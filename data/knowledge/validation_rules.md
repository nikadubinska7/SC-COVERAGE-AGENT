# Validation Rules

## Required validation checks

The agent validates:

- source row count
- included row count
- cancelled row count
- source total
- report total
- reconciliation difference
- missing required values
- unexpected statuses

## Included rows

Rows are included when status is:

- Booked/Shipped
- Available
- Open Order

## Excluded rows

Rows are excluded when status is:

- Cancelled

## Unexpected statuses

Any status outside the included or excluded status lists is flagged as unexpected.

## Reconciliation

The report reconciles when the absolute difference between source total and report total is less than or equal to 0.01.

## Failure behavior

If validation fails, the workflow should return a failure status to N8N.

The workflow should not send a successful notification email when reconciliation fails.