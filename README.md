# Wolfline logger (ISE 537 project)

Logs NC State Wolfline bus positions every 30 seconds from the public GTFS-realtime feed
published by Passio (`https://passio3.com/ncstateuni/passioTransit/gtfs/`), using GitHub Actions,
so no local computer needs to stay on.

## What gets saved
- `data/raw/<date>/run_<time>.csv`: one row per bus per poll (location, trip, route, next stop, crowding).
- `data/gtfs/google_transit_<date>_<hash>.zip`: the scheduled timetable; a new copy appears only when it changes.

Runs start every 2 hours and last about 2h20m, so they overlap; remove duplicate rows by
`vehicle_id` + `vehicle_timestamp`. GitHub sometimes starts scheduled runs late, so expect a few short gaps.

## Stopping
Actions tab → "Log Wolfline positions" → `...` → Disable workflow.

## Loading in R
```r
files <- list.files("data/raw", pattern = "\\.csv$", recursive = TRUE, full.names = TRUE)
pos <- do.call(rbind, lapply(files, read.csv, colClasses = c(trip_id = "character", stop_id = "character")))
pos <- pos[!duplicated(pos[, c("vehicle_id", "vehicle_timestamp")]), ]
pos$time <- as.POSIXct(pos$vehicle_timestamp, origin = "1970-01-01", tz = "America/New_York")

# Scheduled stop times, to compare against actual arrivals
sched_zip <- tail(sort(list.files("data/gtfs", full.names = TRUE)), 1)
stop_times <- read.csv(unz(sched_zip, "stop_times.txt"), colClasses = "character")
```
