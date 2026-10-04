# DS_2_Data-viz
Today, you will display the data
The subject states tha i must plot charts excluding Februay data.



BEGIN;SELECT COUNT(*), MIN(event_time), MAX(event_time)
FROM public.customers
WHERE event_time >= '2023-02-01 00:00:00+01'
  AND event_time <  '2023-03-01 00:00:00+01';END;
