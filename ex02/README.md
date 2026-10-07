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




## box2

### What is the average basket price?

##### Each user_id has several user_sessions.

```sql
SELECT user_id, user_session, price 
FROM customers 
WHERE  event_type = 'purchase' 
   AND event_time < '2023-02-01 00:00:00+01'
   AND user_id = 10280338
ORDER BY user_session;
```


```text
 user_id  |             user_session             | price 
----------+--------------------------------------+-------
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.43
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.27
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.43
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.43
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.43
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.43
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.10
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 5a8ef64a-9215-4c88-ad5f-b3bab4e03fb3 |  1.59
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.27
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.43
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.43
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  0.79
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.59
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.59
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.59
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.43
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.59
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.59
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.43
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.59
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.59
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  0.79
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.59
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.59
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.59
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.59
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.59
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.43
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.43
 10280338 | 9728269f-2014-4d85-a95a-0dab99c4851e |  1.27
 10280338 | bcc9bfa0-8a71-485d-b315-297b0038b4c2 |  1.59
 10280338 | bcc9bfa0-8a71-485d-b315-297b0038b4c2 |  1.59
 10280338 | bcc9bfa0-8a71-485d-b315-297b0038b4c2 |  1.43
 10280338 | bcc9bfa0-8a71-485d-b315-297b0038b4c2 |  5.24
 10280338 | bcc9bfa0-8a71-485d-b315-297b0038b4c2 |  1.59
 10280338 | bcc9bfa0-8a71-485d-b315-297b0038b4c2 |  1.51
 10280338 | bcc9bfa0-8a71-485d-b315-297b0038b4c2 |  1.59
 10280338 | bcc9bfa0-8a71-485d-b315-297b0038b4c2 |  0.24
 10280338 | bcc9bfa0-8a71-485d-b315-297b0038b4c2 |  5.24
 10280338 | bcc9bfa0-8a71-485d-b315-297b0038b4c2 |  5.24
 10280338 | bce6164d-93ef-4d65-ae2f-7ee15552eae7 |  4.56
 10280338 | bce6164d-93ef-4d65-ae2f-7ee15552eae7 |  4.97
 10280338 | bce6164d-93ef-4d65-ae2f-7ee15552eae7 |  4.86
 10280338 | bce6164d-93ef-4d65-ae2f-7ee15552eae7 |  5.08
 10280338 | bce6164d-93ef-4d65-ae2f-7ee15552eae7 |  4.86
 10280338 | bce6164d-93ef-4d65-ae2f-7ee15552eae7 |  5.24
 10280338 | c9cad2fe-9213-42c0-a68a-c329b62f394a | 18.10
```

##### Inside each user_session 

Inside each user_session there are several Purchase records of products wiht price.
The basket price is the sum of prices for a session.

```sql
SELECT user_id, user_session, SUM(price) AS basket_price
FROM customers
WHERE  event_type = 'purchase' 
   AND event_time < '2023-02-01 00:00:00+01'
   AND user_id = 10280338
GROUP BY user_id, user_session;
```

```text
 user_id  |             user_session             | basket_price 
----------+--------------------------------------+--------------
 10280338 | bcc9bfa0-8a71-485d-b315-297b0038b4c2 |        25.26
 10280338 | bce6164d-93ef-4d65-ae2f-7ee15552eae7 |        29.57
 10280338 | c9cad2fe-9213-42c0-a68a-c329b62f394a |        18.10
```
##### Average the basket price 

```sql
SELECT user_id, AVG(basket_price) AS average_basket_price
FROM (
    SELECT user_id, user_session, SUM(price) AS basket_price
    FROM customers
    WHERE event_type = 'purchase' AND 
        event_time < '2023-02-01 00:00:00+01' AND user_id = 10280338
    GROUP BY user_id, user_session
) AS baskets
GROUP BY user_id;
```

```text
 user_id  | average_basket_price 
----------+----------------------
 10280338 |  24.3100000000000000
(1 row)

```

##### Create the first temporal table

The base table has the average basket price for each user id

```sql
CREATE TEMP TABLE base AS (
            SELECT user_id, AVG(basket_price) AS average_basket_price
            FROM (
                SELECT user_id, user_session, SUM(price) AS basket_price
                FROM customers
                WHERE event_type = 'purchase' AND 
                    event_time < '2023-02-01 00:00:00+01'
                GROUP BY user_id, user_session
            ) AS baskets
            GROUP BY user_id);
```


```sql
select * from base limit 5;
```

```text
 user_id  | average_basket_price 
----------+----------------------
  9794320 |  12.6800000000000000
 10079204 |  25.8100000000000000
 10280338 |  35.5660000000000000
 12055855 |  16.5400000000000000
 12936739 |  29.8900000000000000

```
##### Create the second temporal table

This table has only one row. 
It was explained above how 

```sql
CREATE TEMP TABLE quartiles AS (
SELECT
    MIN(average_basket_price) AS min,
    MAX(average_basket_price) AS max,
    q.q1, q.median, q.q3,
    MIN(average_basket_price) FILTER (
        WHERE average_basket_price >= q.q1 - 1.5 * (q.q3 - q.q1)) AS whislo,
    MAX(average_basket_price) FILTER (
        WHERE average_basket_price <= q.q3 + 1.5 * (q.q3 - q.q1)) AS whishi
FROM base                                                                  
CROSS JOIN (
    SELECT
        percentile_cont(0.25) WITHIN GROUP (ORDER BY average_basket_price) AS q1,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY average_basket_price) AS median,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY average_basket_price) AS q3
    FROM base                                                                   
) q          
GROUP BY q.q1, q.median, q.q3);
```


```sql
select * from quartiles;
```

```text
          min           |          max          |  q1   |       median       |  q3   |         whislo         |       whishi        
------------------------+-----------------------+-------+--------------------+-------+------------------------+---------------------
 0.13000000000000000000 | 1738.1000000000000000 | 15.22 | 27.655833333333334 | 47.46 | 0.13000000000000000000 | 95.8200000000000000
(1 row)
```


### Outlieres

```SQL
SELECT DISTINCT b.average_basket_price 
FROM base b CROSS JOIN quartiles q 
WHERE ( (b.average_basket_price < q.q1 - 1.5 * (q.q3 - q.q1) OR
            q.q3 + 1.5 * (q.q3 - q.q1) < b.average_basket_price) );
```