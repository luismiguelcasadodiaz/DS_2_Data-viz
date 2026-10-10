import psycopg
import sys
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt


carpeta_script = Path(__file__).resolve().parent


def subject_print(stats: pd.DataFrame) -> None:
    print(f"{'count':<6}{stats['count'].item():>16.6f}")
    print(f"{'mean':<6}{stats['mean'].item():>16.6f}")
    print(f"{'sta':<6}{stats['std'].item():>16.6f}")
    print(f"{'min':<6}{stats['min'].item():>16.6f}")
    print(f"{'25%':<6}{stats['q1'].item():>16.6f}")
    print(f"{'50%':<6}{stats['median'].item():>16.6f}")
    print(f"{'75%':<6}{stats['q3'].item():>16.6f}")
    print(f"{'max':<6}{stats['max'].item():>16.6f}")                

def box1(bucket_size: int = 10) -> None:

    sql0 = psycopg.sql.SQL("""
        WITH 
        summary AS (
            SELECT DISTINCT 
                DATE(event_time) AS day, 
                user_id  
            FROM purchased_before_feb
            ), 
        gap AS (
            SELECT 
                user_id,
                day - LAG(day) OVER (PARTITION BY user_id ORDER BY day) as dias_entre_compras
            FROM summary
            ),
        base AS (
            SELECT 
                user_id, 
                count(*) as sesiones, 
                AVG(dias_entre_compras) AS average
            FROM gap
            GROUP BY user_id
            ),
        stats AS (
            SELECT 
                count(*), 
                MIN(average) AS lim_inf, 
                MAX(average) as lin_sup
            FROM  base
            ), 
        uniques AS ( 
            SELECT 
                0 AS bin_start,
                1 AS bin_end,
                count(*) as num_users
            FROM base 
            WHERE sesiones = 1
            ), 
        frequents AS (
            SELECT * 
            FROM base 
            WHERE sesiones > 1
            ), 
        param AS (
            SELECT 
                {}::numeric AS bucket_size
            ), 
        semihisto AS ( 
            SELECT 
                (ROUND(f.average / p.bucket_size) * p.bucket_size) + 1 AS bin_start,
                ROUND(f.average / p.bucket_size) * p.bucket_size + p.bucket_size AS bin_end, 
                count(*) AS num_users 
            FROM frequents AS f 
            CROSS JOIN param AS p 
            GROUP BY bin_start, bin_end 
            ORDER BY bin_start
            )
        SELECT * FROM uniques 
        UNION ALL SELECT * FROM semihisto;
        """).format(psycopg.sql.Literal(bucket_size))
    
    with psycopg.connect(
        host="127.0.0.1", port=5432, dbname="piscineds", user="luicasad"
    ) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(sql0)     #  calculate frequency

                # retrieve data from query into DataFrame
                rows = cur.fetchall()
                columns = [desc.name for desc in cur.description]

                da = pd.DataFrame(rows, columns=columns)
                du = da[da["bin_start"] == 0]                
                df = da[da["bin_start"] != 0]

                tot = da["num_users"].sum()
                uni = du["num_users"].sum()                
                fre = df["num_users"].sum() 

                perc = 0.97              
                note = f"{uni} of {tot} users ({100 * uni / tot :.2f}%) purchased only once "
                note += f"and are not shown.\n Histogram covers {perc * 100:.0f}% of the "
                note += f"{fre} repeat buyers (2+ purchases)."

                plt.style.use("seaborn-v0_8-darkgrid")   # grey background + white grid
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.bar(df["bin_start"], df["num_users"], width=bucket_size * 0.90,
                        align="edge", edgecolor="black")
                ax.set_xlabel("Frequency")

                s = (df["num_users"].cumsum() > perc * df["num_users"].sum()).idxmax()
                ax.set_xlim(0, df["bin_end"].tolist()[s+1])
                ax.set_xticks(df["bin_end"].tolist()[:s+2])
                ax.set_ylabel("Customers")
                ax.set_ylim(0, df["num_users"].max() * 1.05)
                ax.yaxis.set_visible(True)
                ax.set_title(f"Distribution of average days between purchase (bucket size = {bucket_size} days). Shows {perc * 100:.0f}%")
                ax.text(0.97, 0.95, note, transform=ax.transAxes, ha="right", va="top", fontsize=10,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.9))
                plt.savefig(carpeta_script /"customers_by_freq.png")
                plt.show()


                
            except Exception as e:
                conn.rollback()
                print(f"Error creating boxplot from prices: {e}")
            finally:
                cur.close()
                conn.commit()
                conn.close()

def box2(bucket_size: int = 50) -> None:

    sql0 = psycopg.sql.SQL("""
        WITH params AS (
            SELECT {}::numeric AS bucket_size   -- default bucket size
        ),
        user_totals AS (
            SELECT user_id, SUM(price) AS total_spent
            FROM purchased_before_feb
            GROUP BY user_id
        )
        SELECT
            ROUND(u.total_spent / p.bucket_size) * p.bucket_size                 AS bin_start,
            ROUND(u.total_spent / p.bucket_size) * p.bucket_size + p.bucket_size AS bin_end,
            COUNT(*)                                                             AS num_users
        FROM user_totals u
        CROSS JOIN params p
        GROUP BY 1, 2
        ORDER BY 1;
        """).format(psycopg.sql.Literal(bucket_size))

    with psycopg.connect(
        host="127.0.0.1", port=5432, dbname="piscineds", user="luicasad"
    ) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(sql0)     # Calculate bucket count

                # retrieve data from query into DataFrame
                rows = cur.fetchall()
                columns = [desc.name for desc in cur.description]
                df = pd.DataFrame(rows, columns=columns)

                plt.style.use("seaborn-v0_8-darkgrid")   # grey background + white grid
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.bar(df["bin_start"], df["num_users"], width=bucket_size * 0.90,
                        align="edge", edgecolor="black")
                ax.set_xlabel("Monetary value in \u20b3")
                perc = 0.97
                s = (df["num_users"].cumsum() > perc * df["num_users"].sum()).idxmax()
                ax.set_xlim(0, df["bin_end"].tolist()[s+1])
                ax.set_xticks(df["bin_end"].tolist()[:s+2])
                ax.set_ylabel("Customers")
                ax.set_ylim(0, df["num_users"].max() * 1.05)
                ax.yaxis.set_visible(True)
                ax.set_title(f"Distribution of purchase totals (bucket size = {bucket_size}). Shows {perc * 100:.0f}%")
                plt.savefig(carpeta_script /"customers_by_spent.png")
                plt.show()

            except Exception as e:
                conn.rollback()
                print(f"Error creating histogram customers by spent {e}")
            finally:
                cur.close()
                conn.commit()
                conn.close()

def main() -> None:
    box1()
    box2()

if __name__ == "__main__":
    num_args = len(sys.argv)
    if num_args == 1:
        main()
    else:
        print("python ./Building.py")
        sys.exit(1)