# SC Coverage Reporting Rules

## Business objective

The SC Coverage Report Agent analyzes Nike/Jordan order coverage for the Snipes retail account.

The report answers whether future customer demand is already covered by booked, shipped, or available product, and how much remains open by season and requested month.

## Included statuses

The report includes:

- Booked/Shipped
- Available
- Open Order

## Excluded statuses

Cancelled orders are excluded from coverage calculations but counted in validation.

## Coverage formula

Coverage percentage is calculated as:

(Booked/Shipped value + Available value) / Total report wholesale value

Where total report wholesale value is:

Booked/Shipped value + Available value + Open Order value

## Report value rule

The report uses `report_wholesale_value` for aggregation.

For Available records, this usually comes from `available_wholesale`.

For Booked/Shipped and Open Order records, this usually comes from `confirmed_wholesale`.

## Timing buckets

Open Order records are grouped into timing buckets using `eta_vs_crd` and `coverage_performance`.

Timing buckets:

- Early/On Time
- +1 week
- +2 weeks
- +3 weeks
- +4 weeks or later

Non-open-order records keep their status as the timing bucket.

## Reconciliation rule

The report passes reconciliation when:

source_total - report_total <= 0.01

If the difference is greater than 0.01, the workflow should fail validation and should not mark the report as successful.

## LLM role

The LLM may summarize results, explain risks, and select tools.

The LLM must not calculate financial totals. All calculations are deterministic Python calculations.