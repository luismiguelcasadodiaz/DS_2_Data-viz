# DS_2_Data-viz

The subject states that I must plot charts including Februay data.

Pay attention that February data are not only in data_2023_feb. 1770 records form first february minute are in January

```sql
BEGIN;SELECT COUNT(*), MIN(event_time), MAX(event_time)
FROM public.data_2023_jan
WHERE event_time >= '2023-02-01 00:00:00+01'
  AND event_time <  '2023-03-01 00:00:00+01';END;
```

```txt
 count |          min           |          max           
-------+------------------------+------------------------
  1770 | 2023-02-01 00:00:03+01 | 2023-02-01 00:59:58+01
(1 row)
```


