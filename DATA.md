# Data

**Published user journey dataset**

- Rows: 1,350 sessions, 898 distinct paths, 16 distinct steps
- Source: nikhilchoudhary28/user-journey-analysis, GitHub
- Licence: public repository; provenance of the underlying sessions is not documented
- Touchpoints are ON-SITE page steps (Homepage, Pricing, Courses, Checkout, Coupon), not paid-media channels. Conversion means a path ending on a terminal value step.

Raw files are **not committed**. Drop the file into `data/` under the name the
script expects, or point a symlink there, then run `python src/main.py`.
