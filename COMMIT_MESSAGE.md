# Fix market day detection issue

## Changes
- Fixed date handling in `is_market_holiday` function to properly identify trading days
- Enhanced timezone handling to ensure consistent behavior across environments
- Added explicit date conversion to handle different date formats/types
- Improved logging to help diagnose market status
- Fixed bug where April 1, 2025 was incorrectly identified as a non-trading day
- Updated both scheduler.py and railway_start.py to use consistent timezone handling
- Added psutil dependency to requirements.txt for process management

## Technical Details
- Added better date normalization in `is_market_holiday`
- Improved explicit timezone handling in IST (Asia/Kolkata)
- Added defensive date type checking and conversion
- Enhanced logging for better diagnostics
- Consistent implementation across all modules

This update resolves the issue where the application was incorrectly showing the next trading day as Wednesday when the current day (Tuesday, April 1, 2025) was a valid trading day. 