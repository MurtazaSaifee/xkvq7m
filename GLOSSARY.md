# Wind Forecast Monitoring

Language for a UK utility's day-ahead purchasing desk. The desk judges how much national wind generation to rely on when it buys power for the next day.

## Time

**Delivery day**:
The UK calendar day for which power is being bought.
_Avoid_: Target day, trading day

**Decision day**:
The day before a delivery day, on which the purchase decision for that delivery day is made.
_Avoid_: Trading day, D-1 (fine as shorthand, but not as a name)

**Decision cutoff**:
The moment on the decision day by which the purchase decision must be made. Only forecasts published at or before it can inform the decision.
_Avoid_: Deadline, decision time, gate closure (the market's gate closure may set the cutoff, but the two are distinct concepts)

**Target time**:
The start of the half-hour that a generation value, actual or forecast, refers to.
_Avoid_: Start time, delivery time, settlement time

**Publish time**:
The moment a forecast was created.
_Avoid_: Issue time, forecast time, creation time

**Forecast horizon**:
How far ahead a forecast looks: its target time minus its publish time.
_Avoid_: Lead time, lookahead

## Generation

**Actual generation**:
The measured national wind generation for a target time.
_Avoid_: Outturn, actuals (in prose, fine), real generation

**Forecast**:
A predicted national wind generation value for one target time, made at one publish time that is no later than the target time. A target time has many forecasts.
_Avoid_: Prediction, estimate

**Forecast run**:
All forecasts sharing one publish time. A run covers a fixed window of target times several days long.
_Avoid_: Forecast batch, vintage, publication

**Decision forecast**:
For a target time, the latest forecast published at or before the decision cutoff of its delivery day. It is the forecast the desk actually had when it decided.
_Avoid_: Latest forecast (ambiguous: latest as of when?), current forecast

**Decision snapshot**:
All decision forecasts for one delivery day: the wind outlook as the desk saw it at the decision cutoff.
_Avoid_: Forecast vintage, latest run

## Accuracy

**Forecast error**:
Forecast minus actual generation for the same target time. A positive error means wind was over-forecast and the desk relied on wind that didn't arrive.
_Avoid_: Residual, deviation, miss

**Expected-error band**:
The range around a decision snapshot within which actual generation is expected to fall. It is derived only from forecast errors already known at the decision cutoff: those of the 14 delivery days that end two days before the snapshot's delivery day (D-15 to D-2). Nothing from the decision day or later is used.
_Avoid_: Confidence interval, uncertainty band, error bars

**Band coverage**:
The share of target times whose actual generation fell inside its expected-error band. It shows whether the band can be trusted.
_Avoid_: Hit rate, calibration score
