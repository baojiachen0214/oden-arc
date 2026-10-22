# A small smoothing lesson

This is synthetic tutorial material, not a production finding.

## Definition
An exponentially smoothed value follows y_t = alpha*x_t + (1-alpha)*y_(t-1).
Here x_t is the new observation, y_(t-1) the previous smoothed value, and alpha a dimensionless parameter in [0,1]. The observations and smoothed values must use the same units. An initial value must be chosen.

## Worked example
With alpha=0.25, x_t=12 and y_(t-1)=8, the updated value is 9. These numbers are invented for this tutorial.

## Limits
A smaller alpha gives less weight to the new observation. Smoothing alone does not establish predictive accuracy, causal effects or production suitability.
