import psycopg
import sys
import pandas as pd
import matplotlib.pyplot as plt


def main(refresh: bool):

    sql0 = psycopg.sql.SQL("""
        SELECT EXISTS (SELECT 1 FROM pg_matviews 
        WHERE matviewname = 'purchase_price_stats');
        """)
    sql1 = psycopg.sql.SQL("""
        SET work_mem = '512MB';
        SET max_parallel_workers_per_gather = 0;

        CREATE MATERIALIZED VIEW IF NOT EXISTS purchase_price_stats AS
        WITH base AS (
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
            min(price) FILTER (WHERE q.q1 - 1.5 * (q.q3 - q.q1) <= price) AS whislo,
            max(price) FILTER (WHERE price <= q.q3 + 1.5 * (q.q3 - q.q1)) AS whishi,
            count(*)   FILTER (WHERE price <  q.q1 - 1.5 * (q.q3 - q.q1)
                                OR price >  q.q3 + 1.5 * (q.q3 - q.q1)) AS n_outliers
        FROM base CROSS JOIN q
        GROUP BY q.q1, q.median, q.q3;
        SELECT 1
        """)

    sql2 = psycopg.sql.SQL("""
        SELECT count, mean, std, min, q1, median, q3, max,whislo, whishi, n_outliers FROM purchase_price_stats;
        """)
    sql3 = psycopg.sql.SQL("REFRESH MATERIALIZED VIEW purchase_price_stats;")

    sql4 = psycopg.sql.SQL("""
        SELECT DISTINCT c.price 
        FROM customers c CROSS JOIN purchase_price_stats s 
        WHERE   c.event_time < '2023-02-01 00:00:00+01' AND 
                c.event_type = 'purchase' AND 
                ( (c.price < s.q1 - 1.5 * (s.q3 - s.q1) OR
                   s.q3 + 1.5 * (s.q3 - s.q1) < c.price) );
        """)

    with psycopg.connect(
        host="127.0.0.1", port=5432, dbname="piscineds", user="luicasad"
    ) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(sql0)     #  Check existence
                exists = cur.fetchone()[0]
                if not exists:
                    print("Creating view")
                    cur.execute(sql1) #  View creation
                    print("Retriving data")
                    cur.execute(sql2) #  Retrieve data
                elif refresh:
                    print("Refreshing view")
                    cur.execute(sql3) #  Refresh view
                    print("Retriving data")
                    cur.execute(sql2) #  Retrieve data
                else:
                    print("Retriving data")
                    cur.execute(sql2) #  Retrieve data

                # retrieve data from query into DataFrame
                rows = cur.fetchall()
                columns = [desc.name for desc in cur.description]
                stats = pd.DataFrame(rows, columns=columns)
                print(stats)
                cur.execute(sql4)
                rows = cur.fetchall()
                columns = [desc.name for desc in cur.description]
                fliers = pd.DataFrame(rows, columns=columns).to_numpy()

                box = {
                    "label": "price",
                    "med": stats["median"], "q1": stats["q1"], "q3": stats["q3"],
                    "whislo": stats["whislo"], "whishi": stats["whishi"],
                    "fliers": fliers,
                }

                fig, ax = plt.subplots()
                ax.bxp([box], orientation="horizontal")   
                ax.set_xlabel("price")
                plt.savefig("box.png")
                plt.show()

            except Exception as e:
                conn.rollback()
                print(f"Error creating pie chart from evet_types: {e}")
            finally:
                cur.close()
                conn.commit()
                conn.close()


if __name__ == "__main__":
    num_args = len(sys.argv)
    if num_args == 1:
        main(False)
    elif num_args == 2:
        main(True)
    else:
        print("python ./mustache.py")
        sys.exit(1)

