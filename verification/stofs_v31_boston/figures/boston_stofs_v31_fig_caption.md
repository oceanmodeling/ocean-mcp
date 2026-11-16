**Figure. STOFS v3.1 forecast water level at Boston, MA (NOAA CO-OPS 8443970), cycle 2026-10-30 12:00 UTC.**
(A) Observed water level and the STOFS-2D-Global and STOFS-3D-Atlantic station forecasts for the
same 480 six-minute valid times, 2026-10-30 12:06 to 2026-11-01 12:00 UTC (forecast lead 0 < lead ≤ 48 h;
lead time on the top axis). (B) Signed error, model − observed. Model values are the NOAA station NetCDF
products (STOFS-2D-Global `STOFS_2D_GLOBAL.V3.1.0`, referenced to local mean sea level, LMSL, per NOAA
documentation; STOFS-3D-Atlantic `stofs.v3.1.6`, LMSL per the file's `zeta` metadata). Observations are
NOAA CO-OPS 6-minute water levels on the station's mean sea level datum (MSL, 1983–2001 tidal epoch);
they are **preliminary** and may be revised. Pairs are exact timestamp matches; no vertical offset or
transformation is applied. Both products are operationally **bias-corrected with recent CO-OPS
observations** (STOFS-2D-Global: station correction from the previous 5 days of nowcast bias;
STOFS-3D-Atlantic: open-boundary adjustment from the 2-day nowcast bias at 11 East Coast stations), so the
comparison describes corrected operational guidance, not independent model skill. The STOFS-3D error is
dominated by tidal phase and amplitude (best-correlated lag +12 min, model later; model
standard deviation 12.5% above observed; the mean bias contributes 34% of the
mean squared error) rather than a constant offset; the STOFS-2D lag is −12 min.
Statistics are given in Table X. Inputs: station NetCDF SHA-256
`f1ed4e592982…` (2D) and `4660819425aa…` (3D); CO-OPS
response `c207c8013890…` (full checksums and URLs in the archived manifest).
