## Source table

Table name:

```text
orderbook

The table contains mock orderbook records derived from the Excel ORDERBOOK worksheet.

MVP fields
Field	Type	Purpose
id	integer or UUID	Unique record identifier
banner	text	Retail account or client name
sold_to_name	text	Sold-to customer name
sold_to_code	text	Sold-to customer code
ship_to_name	text	Ship-to customer name
ship_to_code	text	Ship-to customer code
brand	text	Nike or Jordan
age_division	text	Product age or division segment
season	text	Product season such as SP2026, SU2026, FA2026, HO2026
order_type	text	Order type, usually Standard Order - Futures
status	text	Booked/Shipped, Available, Open Order, Cancelled
order_entry_date	date	Date order was entered
customer_request_date	date	Customer requested delivery date
requested_month	text	Requested month reporting bucket
customer_confirmed_date	date	Customer confirmed date
eta	date	Estimated delivery or availability date
eta_vs_crd	text or numeric	ETA compared with customer request date
week_commencing	date	Weekly reporting bucket
coverage_performance	text	Timing status or coverage performance bucket
confirmed_wholesale	numeric	Confirmed wholesale value
available_wholesale	numeric	Available wholesale value
quantity	numeric	Optional quantity field, only used if confirmed
Required fields for MVP

The MVP requires:

banner
season
order_type
status
requested_month
confirmed_wholesale
available_wholesale
Optional fields for MVP

The MVP can use these fields if available:

eta
eta_vs_crd
customer_request_date
coverage_performance
brand
age_division
quantity
Field naming rule

All source column names should be normalized before loading into Supabase:

lowercase
spaces replaced with underscores
special characters removed
consistent date format
numeric values converted to decimals

Example:

Confirmed Wholesale → confirmed_wholesale
Requested Month → requested_month
ETA vs CRD → eta_vs_crd
Data quality checks

The workflow checks for:

missing required fields;
null season values;
null status values;
invalid numeric values;
invalid dates;
unexpected status names;
source total versus report total difference.