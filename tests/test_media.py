from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from oden_arc.common import SkillError, digest, load_json
from oden_arc.media import crop_image, crop_pdf
try:
    from PIL import Image, ImageOps, PngImagePlugin
    HAS_IMAGES = True
except ImportError:
    HAS_IMAGES = False
try:
    import fitz
    HAS_PDF = True
except ImportError:
    HAS_PDF = False


@unittest.skipUnless(HAS_IMAGES, 'Install the images extra to run image tests')
class MediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.base=Path(self.tmp.name)
        self.img=Image.new('RGBA',(80,60),(120,30,70,120)); self.path=self.base/'sample.png'; self.img.save(self.path)
    def tearDown(self): self.tmp.cleanup()
    def test_image_crop_provenance_and_alpha(self):
        r=crop_image(self.path,self.base/'out',[10,5,70,50])['record']
        im=Image.open(self.base/'out/crop.png')
        self.assertEqual(im.size,(60,45)); self.assertEqual(im.mode,'RGBA')
        self.assertEqual(r['output']['sha256'],digest((self.base/'out/crop.png').read_bytes()))
        self.assertEqual(r['source']['sha256'],digest(self.path.read_bytes()))
    def test_no_output_overwrite(self):
        crop_image(self.path,self.base/'out',[0,0,80,60])
        with self.assertRaises(SkillError): crop_image(self.path,self.base/'out',[0,0,10,10])
    def test_invalid_crop_boxes(self):
        for box in ([0,0,81,60],[-1,0,10,10],[0,0,0,10],[0,0,float('nan'),1],[0,0,1.1,2]):
            with self.subTest(box=box), self.assertRaises(SkillError): crop_image(self.path,self.base/'out',box)
    def test_source_hash_guard(self):
        with self.assertRaises(SkillError): crop_image(self.path,self.base/'out',[0,0,20,20],expected_sha='0'*64)
    def test_exif_orientations(self):
        # Eight display orientations are checked against independent full-image transpose.
        im=Image.new('RGB',(8,6)); im.putdata([(i%256,(i*7)%256,(i*13)%256) for i in range(48)])
        for orientation in range(1,9):
            with self.subTest(orientation=orientation):
                p=self.base/f'exif{orientation}.png'; exif=im.getexif(); exif[274]=orientation; im.save(p,exif=exif)
                with Image.open(p) as f: expected=ImageOps.exif_transpose(f).copy()
                out=self.base/f'o{orientation}'; crop_image(p,out,[0,0,expected.width,expected.height])
                with Image.open(out/'crop.png') as actual: self.assertEqual(actual.tobytes(),expected.tobytes())
    def test_gamma_and_profile_retained(self):
        import struct
        pi=PngImagePlugin.PngInfo(); pi.add(b'gAMA',struct.pack('>I',45455))
        self.img.save(self.path,pnginfo=pi,icc_profile=b'test-profile-marker')
        crop_image(self.path,self.base/'out',[0,0,20,20])
        with Image.open(self.base/'out/crop.png') as im:
            self.assertAlmostEqual(im.info['gamma'],.45455)
            self.assertEqual(im.info['icc_profile'],b'test-profile-marker')
    def test_cmyk_rejected_not_silently_converted(self):
        p=self.base/'cmyk.jpg'; Image.new('CMYK',(10,10)).save(p)
        with self.assertRaises(SkillError): crop_image(p,self.base/'out',[0,0,10,10])
    def test_animated_input_requires_explicit_frame(self):
        p=self.base/'motion.gif'; im=Image.new('RGB',(10,10),'red'); im2=Image.new('RGB',(10,10),'blue')
        im.save(p,save_all=True,append_images=[im2],duration=100,loop=0)
        with self.assertRaises(SkillError): crop_image(p,self.base/'out',[0,0,10,10])
        self.assertTrue(crop_image(p,self.base/'frame',[0,0,10,10],frame=1)['ok'])
    def make_pdf(self,rotation=0,cropbox=False):
        p=self.base/f'r{rotation}-{cropbox}.pdf'; doc=fitz.open(); page=doc.new_page(width=180,height=120)
        page.draw_rect(fitz.Rect(10,10,80,80),fill=(1,0,0)); page.insert_text((20,100),'SYNTHETIC EVIDENCE')
        if cropbox: page.set_cropbox(fitz.Rect(10,5,170,115))
        page.set_rotation(rotation); doc.save(p); doc.close(); return p
    @unittest.skipUnless(HAS_PDF, 'PDF tests need the separately licensed pdf extra')
    def test_pdf_rotations_and_cropbox(self):
        for rot in (0,90,180,270):
            with self.subTest(rotation=rot):
                p=self.make_pdf(rot,True)
                with fitz.open(p) as doc:
                    rect=doc[0].rect; pix=doc[0].get_pixmap(dpi=72,alpha=False,annots=False,colorspace=fitz.csRGB)
                    expected=Image.frombytes('RGB',(pix.width,pix.height),pix.samples).crop((10,10,50,50))
                out=self.base/f'out{rot}'; r=crop_pdf(p,out,1,[10,10,50,50],dpi=72)
                with Image.open(out/'crop.png') as actual: self.assertEqual(actual.tobytes(),expected.tobytes())
                self.assertEqual(r['record']['source']['rotation'],rot)
    @unittest.skipUnless(HAS_PDF, 'PDF tests need the separately licensed pdf extra')
    def test_pdf_page_and_budget_guard(self):
        p=self.make_pdf()
        with self.assertRaises(SkillError): crop_pdf(p,self.base/'out',2,[0,0,10,10])
        with self.assertRaises(SkillError): crop_pdf(p,self.base/'out',1,[0,0,10,10],dpi=900)
    @unittest.skipUnless(HAS_PDF, 'PDF tests need the separately licensed pdf extra')
    def test_encrypted_pdf_refused(self):
        p=self.base/'protected.pdf'; doc=fitz.open(); doc.new_page()
        doc.save(p,encryption=fitz.PDF_ENCRYPT_AES_256,owner_pw='owner',user_pw='reader'); doc.close()
        with self.assertRaises(SkillError): crop_pdf(p,self.base/'out',1,[0,0,10,10])


if __name__ == '__main__': unittest.main()
