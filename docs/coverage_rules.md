# Coverage Rules

## Purpose

This document defines the business rules used by the SC Coverage Report Agent.

## Coverage definition

Coverage measures how much customer demand is already fulfilled, available to fulfill, or still open.

The main coverage categories are:

1. Booked/Shipped
2. Available
3. Open Order

## Included records

Include records where status is one of:

- Booked/Shipped
- Available
- Open Order

## Excluded records

Exclude records where status is:

- Cancelled

Cancelled records are not included in the coverage calculation, but they are counted in the validation output.

## Mandatory financial metric

The MVP uses wholesale value as the primary metric.

Primary amount fields:

- Confirmed wholesale value
- Available wholesale value

If a record is Booked/Shipped or Open Order, confirmed wholesale value is used.

If a record is Available, available wholesale value is used when applicable.

## Coverage percentage

Coverage percentage is calculated as:

```text
(Booked/Shipped value + Available value) / Total demand value

Where total demand value is:

Booked/Shipped value + Available value + Open Order value
Open-order timing buckets

Open orders are assigned to timing buckets based on delivery timing risk:

Early/On Time
+1 week
+2 weeks
+3 weeks
+4 weeks or later

The exact logic depends on the available source field:

Preferred field:

eta_vs_crd

Fallback fields:

eta
customer_request_date
Season grouping

The report groups data by season, such as:

SP2026
SU2026
FA2026
HO2026
Requested month grouping

Requested month is used as the monthly coverage bucket.

Preferred source field:

requested_month

Fallback logic:

derive YYYY-MM from customer_request_date
Reconciliation rule

The report must reconcile the source total to the report total.

Maximum acceptable monetary difference:

0.01

If the difference is greater than 0.01, the report validation fails and the workflow should not publish the report as successful.

LLM usage rule

The LLM must not calculate financial totals.

All calculations are performed by deterministic Python functions.

The LLM may be used for:

choosing tools;
explaining validation issues;
generating short observations;
summarizing the final report.