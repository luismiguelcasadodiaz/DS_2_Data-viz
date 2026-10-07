# three tables

We create two tables to cross join them later.

##### The first table: bucket size

We create a table with only a row

```sql
SELECT 50::numeric AS bucket_size;
```

```text
 bucket_size 
-------------
          50
(1 row)
```

##### The second table: total spent by user

Excluding february, groups `purchase`records by `user_id` adding all product's prices.

```sql
SELECT user_id, SUM(price) AS total_spent
    FROM customers
    WHERE event_type = 'purchase'
      AND event_time < '2023-02-01 00:00:00+01'
    GROUP BY user_id
```

```text
  user_id  |total_spent   
-----------+-----------
 150318419 |     3162.90
 557790271 |     2715.87
 469299888 |     2247.33
 247216055 |     1807.91
 400911344 |     1364.52
 394666389 |      808.61
 518278060 |      797.76
```

##### The cross join: the base to calculate count by bucket

```text
  user_id  |total_spent|  bucket_size 
-----------+-----------+-------------
 150318419 |   3162.90 |      50
 557790271 |   2715.87 |      50
 469299888 |   2247.33 |      50
 247216055 |   1807.91 |      50
 400911344 |   1364.52 |      50
 394666389 |    808.61 |      50
 518278060 |    797.76 |      50
```

##### The mathematical operations

```sql
FLOOR(u.total_spent / p.bucket_size) * p.bucket_size                 AS bin_start,
FLOOR(u.total_spent / p.bucket_size) * p.bucket_size + p.bucket_size AS bin_end,
```

```text

FLOOR(3162.90  / 50) * 50      AS bin_start,
FLOOR(3162.90  / 50) * 50 + 50 AS bin_end,

FLOOR(63,258) * 50      AS bin_start,
FLOOR(63,258) * 50 + 50 AS bin_end,

63 * 50      AS bin_start,
63 * 50 + 50 AS bin_end,

3150      AS bin_start
3150 + 50 AS bin_end

3150 AS bin_start
3200 AS bin_end
```


```text
  user_id  |total_spent|  bucket_size  | bin_start | bin_end |
-----------+-----------+---------------+-----------+--------- 
 150318419 |   3162.90 |      50       |   3 150   |  3 200   
 557790271 |   2715.87 |      50       |           |          
 469299888 |   2247.33 |      50       |           |          
 247216055 |   1807.91 |      50       |           |            
 400911344 |   1364.52 |      50       |           |            
 394666389 |    808.61 |      50       |     800   |    850
 518278060 |    797.76 |      50       |     750   |    800
```
##### Group by bucket limits and count

```sql
SELECT
    FLOOR(u.total_spent / p.bucket_size) * p.bucket_size                 AS bin_start,
    FLOOR(u.total_spent / p.bucket_size) * p.bucket_size + p.bucket_size AS bin_end,
    COUNT(*)                                                             AS num_users
FROM user_totals u
CROSS JOIN params p
GROUP BY 1, 2
```

##### all together


```sql
WITH params AS (
    SELECT 50::numeric AS bucket_size   -- default bucket size
),
user_totals AS (
    SELECT user_id, SUM(price) AS total_spent
    FROM customers
    WHERE event_type = 'purchase'
      AND event_time < '2023-02-01 00:00:00+01'
    GROUP BY user_id
)
SELECT
    FLOOR(u.total_spent / p.bucket_size) * p.bucket_size                 AS bin_start,
    FLOOR(u.total_spent / p.bucket_size) * p.bucket_size + p.bucket_size AS bin_end,
    COUNT(*)                                                             AS num_users
FROM user_totals u
CROSS JOIN params p
GROUP BY 1, 2
ORDER BY 1;
```