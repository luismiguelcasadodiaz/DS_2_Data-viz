After customer's duplicates removal and join with distinct items we have  19 175 899 records. 

They are too many records to use the Pandas dataframes. In general, delegating to SQL is more efficient.


### Why SQL Wins

The bottleneck is almost never computation, but rather data transfer. If you read the entire price column, PostgreSQL has to send all the rows across the network, the driver (psycopg2, etc.) has to convert each value into a Python object, and pandas has to build the DataFrame in memory. With millions of purchases, that takes seconds and a fair amount of RAM. Instead, if you calculate the quartiles in the database, only a single row travels. In addition, with a materialized view, the calculation is done once and stays saved.

Pandas is only worthwhile when the data is small (hundreds of thousands of rows, more or less), where the difference is negligible and simplicity outweighs performance, or when you are going to perform many different analyses on the same column and it pays off to load it just once.

### Let's analyze the query

1.- Create a table named `base` to calculate later on it. This base table takes only the prices of products **purchased before February**.

2.- Create a table named `quartiles` from `base` to calculate the percentiles. To calculate percentiles data has to be ordered. THis is done with "WITHIN GROUP (ORDER BY price)" that can be read as **within the group of rows to be used in the aggregate function percentile_cont order them by price**. Percentile_cont means continue. it returns a calculated/interpolated value that match the funciton argument when does not fall exactly over one price. Quartiles is a table wiht only one line.

3.- Cross join the base table with quartiles table. This will add to each row of the base table the 3 values form quartiles, in such a way that each price can be compared against the whiskers values. "FILTER (WHERE ...)" is like a per-column WHERE. The minimal price of the prices is calculated over the rows that match the condition where.

```text
base            q                    base CROSS JOIN q
price           q1   median  q3      price  q1   median  q3
-----           ---  ------  ---     -----  ---  ------  ---
  2.0           1.5  3.0     6.0       2.0  1.5  3.0     6.0
  5.0      ×                    =      5.0  1.5  3.0     6.0
 40.0                                 40.0  1.5  3.0     6.0
```

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS purchase_price_stats AS
WITH base AS (
    SELECT price
    FROM customers
    WHERE event_time < '2023-02-01 00:00:00+01'
      AND event_type = 'purchase'
),
quartiles AS (
    SELECT
        percentile_cont(0.25) WITHIN GROUP (ORDER BY price) AS q1,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY price) AS median,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY price) AS q3
    FROM base
)
SELECT
    count(*)                    AS count,
    round(avg(price), 2)        AS mean,
    round(stddev(price), 2)     AS std,
    min(price)                  AS min,
    q.q1, q.median, q.q3,
    max(price)                  AS max,
    min(price) FILTER (WHERE q.q1 - 1.5 * (q.q3 - q.q1) <= price) AS whislo,
    max(price) FILTER (WHERE price <= q.q3 + 1.5 * (q.q3 - q.q1)) AS whishi,
    count(*)   FILTER (WHERE price <  q.q1 - 1.5 * (q.q3 - q.q1)
                          OR price >  q.q3 + 1.5 * (q.q3 - q.q1)) AS n_outliers
FROM base CROSS JOIN q
GROUP BY q.q1, q.median, q.q3;
SELECT 1
```



### Creating indexex

piscineds=# WITH base AS (
    SELECT price
    FROM customers
    WHERE event_time < '2023-02-01 00:00:00+01'
      AND event_type = 'purchase'
),                               
q AS (
    SELECT
        percentile_cont(0.25) WITHIN GROUP (ORDER BY price) AS q1,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY price) AS median,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY price) AS q3
    FROM base                                                    
)            
SELECT
    count(*)                    AS count,
    round(avg(price), 2)        AS mean,
    round(stddev(price), 2)     AS std,
    min(price)                  AS min,
    q.q1, q.median, q.q3,
    max(price)                  AS max,
    min(price) FILTER (WHERE price >= q.q1 - 1.5 * (q.q3 - q.q1)) AS whislo,
    max(price) FILTER (WHERE price <= q.q3 + 1.5 * (q.q3 - q.q1)) AS whishi,
    count(*)   FILTER (WHERE price <  q.q1 - 1.5 * (q.q3 - q.q1)
                          OR price >  q.q3 + 1.5 * (q.q3 - q.q1)) AS n_outliers
FROM base CROSS JOIN q                                                         
GROUP BY q.q1, q.median, q.q3;
  count  | mean | std  |  min   |  q1  | median | q3  |  max   | whislo | whishi | n_outliers 
---------+------+------+--------+------+--------+-----+--------+--------+--------+------------
 1044100 | 4.92 | 8.85 | -79.37 | 1.59 |      3 | 5.4 | 327.78 |   0.00 |  11.11 |      73738
(1 row)

Time: 8214.452 ms (00:08.214)
piscineds=# CREATE INDEX idx_customers_type_time
    ON customers (event_type, event_time)
    INCLUDE (price);
CREATE INDEX
Time: 24732.966 ms (00:24.733)
piscineds=# WITH base AS (
    SELECT price                         
    FROM customers
    WHERE event_time < '2023-02-01 00:00:00+01'
      AND event_type = 'purchase'
),
q AS (
    SELECT
        percentile_cont(0.25) WITHIN GROUP (ORDER BY price) AS q1,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY price) AS median,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY price) AS q3
    FROM base
)
SELECT
    count(*)                    AS count,
    round(avg(price), 2)        AS mean,
    round(stddev(price), 2)     AS std,
    min(price)                  AS min,
    q.q1, q.median, q.q3,
    max(price)                  AS max,
    min(price) FILTER (WHERE price >= q.q1 - 1.5 * (q.q3 - q.q1)) AS whislo,
    max(price) FILTER (WHERE price <= q.q3 + 1.5 * (q.q3 - q.q1)) AS whishi,
    count(*)   FILTER (WHERE price <  q.q1 - 1.5 * (q.q3 - q.q1)
                          OR price >  q.q3 + 1.5 * (q.q3 - q.q1)) AS n_outliers
FROM base CROSS JOIN q
GROUP BY q.q1, q.median, q.q3;
  count  | mean | std  |  min   |  q1  | median | q3  |  max   | whislo | whishi | n_outliers 
---------+------+------+--------+------+--------+-----+--------+--------+--------+------------
 1044100 | 4.92 | 8.85 | -79.37 | 1.59 |      3 | 5.4 | 327.78 |   0.00 |  11.11 |      73738
(1 row)

Time: 3791.853 ms (00:03.792)
