import psycopg
import sys
import pandas as pd
import matplotlib.pyplot as plt


def subject_print(stats: pd.DataFrame) -> None:
    print(f"{'count':<6}{stats['count'].item():>16.6f}")
    print(f"{'mean':<6}{stats['mean'].item():>16.6f}")
    print(f"{'sta':<6}{stats['std'].item():>16.6f}")
    print(f"{'min':<6}{stats['min'].item():>16.6f}")
    print(f"{'25%':<6}{stats['q1'].item():>16.6f}")
    print(f"{'50%':<6}{stats['median'].item():>16.6f}")
    print(f"{'75%':<6}{stats['q3'].item():>16.6f}")
    print(f"{'max':<6}{stats['max'].item():>16.6f}")                

def box1(refresh: bool):

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
                subject_print(stats)
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
                # plt.style.use("seaborn-v0_8-darkgrid")   # grey background + white grid
                fig, ax = plt.subplots()
                ax.bxp([box],
                        orientation="horizontal",
                        widths=0.8,                           # wide box like seaborn
                        patch_artist=True,                    # allows filling the box
                        # boxprops=dict(facecolor="green", edgecolor="dimgray"),
                        # medianprops=dict(color="dimgray"),
                        # whiskerprops=dict(color="dimgray"),
                        # capprops=dict(color="dimgray"),
                        # flierprops=dict(marker="D", markersize=4,
                        # markerfacecolor="dimgray", markeredgecolor="dimgray"),
                        )
                ax.set_yticks([])                         # remove the "price" label on the left
                ax.set_xlabel("price")
                ax.set_xlim(0, 12)
                plt.savefig("box1.png")
                plt.show()

            except Exception as e:
                conn.rollback()
                print(f"Error creating boxplot from prices: {e}")
            finally:
                cur.close()
                conn.commit()
                conn.close()

def box2(refresh: bool):

    sql0 = psycopg.sql.SQL("""
        SELECT EXISTS (SELECT 1 FROM pg_matviews 
        WHERE matviewname = 'average_basket_price');
        """)
    sql1 = psycopg.sql.SQL("""
        SET work_mem = '512MB';
        SET max_parallel_workers_per_gather = 0;

        DROP TABLE IF EXISTS base;
        DROP TABLE IF EXISTS quartiles;

        CREATE TEMP TABLE base AS (
            SELECT user_id, AVG(basket_price) AS average_basket_price
            FROM (
                SELECT user_id, user_session, SUM(price) AS basket_price
                FROM customers
                WHERE event_type = 'purchase' AND price > 0 AND
                    event_time < '2023-02-01 00:00:00+01'
                GROUP BY user_id, user_session
            ) AS baskets
            GROUP BY user_id);

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
        GROUP BY q.q1, q.median, q.q3);SELECT * FROM quartiles;

        """)

    sql2 = psycopg.sql.SQL("""
        SELECT min, max, q1, median, q3, whislo, whishi FROM quartiles;
        """)
    sql3 = psycopg.sql.SQL("REFRESH MATERIALIZED VIEW average_basket_price;")

    sql4 = psycopg.sql.SQL("""
        SELECT DISTINCT b.average_basket_price 
        FROM base b CROSS JOIN quartiles q 
        WHERE ( (b.average_basket_price < q.q1 - 1.5 * (q.q3 - q.q1) OR
                   q.q3 + 1.5 * (q.q3 - q.q1) < b.average_basket_price) );
        """)

    with psycopg.connect(
        host="127.0.0.1", port=5432, dbname="piscineds", user="luicasad"
    ) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(sql0)     #  Check existence
                exists = cur.fetchone()[0]
                if not exists:
                    print("Creating view for box2")
                    cur.execute(sql1) #  View creation
                    print("Retriving data for box2")
                    cur.execute(sql2) #  Retrieve data
                elif refresh:
                    print("Refreshing view for box2")
                    cur.execute(sql3) #  Refresh view
                    print("Retriving data for box2")
                    cur.execute(sql2) #  Retrieve data
                else:
                    print("Retriving data for box2")
                    cur.execute(sql2) #  Retrieve data

                # retrieve data from query into DataFrame
                rows = cur.fetchall()
                columns = [desc.name for desc in cur.description]
                stats = pd.DataFrame(rows, columns=columns)
                
                cur.execute(sql4)
                rows = cur.fetchall()
                columns = [desc.name for desc in cur.description]
                fliers = pd.DataFrame(rows, columns=columns).to_numpy()

                box = {
                    "label": "Averoge basket price",
                    "med": stats["median"], "q1": stats["q1"], "q3": stats["q3"],
                    "whislo": stats["whislo"], "whishi": stats["whishi"],
                    "fliers": fliers,
                }
                plt.style.use("seaborn-v0_8-darkgrid")   # grey background + white grid
                fig, ax = plt.subplots()
                ax.bxp([box],
                        orientation="horizontal",
                        widths=0.8,                           # wide box like seaborn
                        patch_artist=True,                    # allows filling the box
                        boxprops=dict(facecolor="#7AADD1", edgecolor="dimgray"),
                        medianprops=dict(color="dimgray"),
                        whiskerprops=dict(color="dimgray"),
                        capprops=dict(color="dimgray"),
                        flierprops=dict(marker="D", markersize=4,
                        markerfacecolor="dimgray", markeredgecolor="dimgray")
                        )
                ax.set_yticks([])                         # remove the "price" label on the left
                ax.set_xlim(0, 100)
                ax.set_xlabel("Average basket price")
                plt.savefig("box2.png")
                plt.show()

            except Exception as e:
                conn.rollback()
                print(f"Error creating boxplot from average basket price: {e}")
            finally:
                cur.close()
                conn.commit()
                conn.close()

def main(refresh: bool) -> None:
    box1(refresh)
    box2(refresh)

if __name__ == "__main__":
    num_args = len(sys.argv)
    if num_args == 1:
        main(False)
    elif num_args == 2:
        main(True)
    else:
        print("python ./mustache.py")
        sys.exit(1)

