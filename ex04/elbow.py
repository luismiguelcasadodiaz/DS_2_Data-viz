import psycopg
import sys
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans


carpeta_script = Path(__file__).resolve().parent

def main() -> None:
    sql0 = psycopg.sql.SQL("""
        CREATE TABLE user_features_raw AS
        WITH base AS (
                SELECT 
                    user_id, 
                    COUNT(DISTINCT category_id) AS noc, 
                    NULLIF(COUNT(DISTINCT user_session),0) AS nos, 
                    COUNT(DISTINCT product_id) AS ndp, 
                    COUNT(product_id) AS noi, 
                    SUM(price) AS tvp, 
                    '2023-03-01' - MAX(event_time)::date as dlp,
                    '2023-03-01' - MIN(event_time)::date as dfp,
                     MAX(event_time)::date - MIN(event_time)::date as span           
                FROM customers
                WHERE event_type = 'purchase' AND price > 0
                GROUP BY user_id
            ) 
            SELECT 
                    *, 
                    tvp / nos AS atv, 
                    tvp / noi AS aiv,
                    COALESCE(span::numeric / NULLIF(nos - 1, 0), 0) AS adbp  -- Zero if purchased once 
                FROM base;

        CREATE TABLE user_features AS
        WITH scaled AS (
                SELECT
                    user_id,
                    LN(1 + noc) AS noc,
                    LN(1 + nos) AS nos,
                    LN(1 + ndp) AS ndp,
                    LN(1 + noi) AS noi,
                    LN(1 + tvp) AS tvp,
                    LN(1 + dlp) AS dlp,
                    LN(1 + dfp) AS dfp,            
                    LN(1 + atv) AS atv,
                    LN(1 + aiv) AS aiv,
                    LN(1 + adbp) AS adbp
                FROM user_features_raw
                )
        SELECT
            user_id,
            (noc - min(noc) OVER ()) / NULLIF(MAX(noc) OVER () - MIN(noc) OVER(), 0) AS noc,
            (nos - min(nos) OVER ()) / NULLIF(MAX(nos) OVER () - MIN(nos) OVER(), 0) AS nos,
            (ndp - min(ndp) OVER ()) / NULLIF(MAX(ndp) OVER () - MIN(ndp) OVER(), 0) AS ndp,
            (noi - min(noi) OVER ()) / NULLIF(MAX(noi) OVER () - MIN(noi) OVER(), 0) AS noi,
            (tvp - min(tvp) OVER ()) / NULLIF(MAX(tvp) OVER () - MIN(tvp) OVER(), 0) AS tvp,
            (dlp - min(dlp) OVER ()) / NULLIF(MAX(dlp) OVER () - MIN(dlp) OVER(), 0) AS dlp,
            (dfp - min(dfp) OVER ()) / NULLIF(MAX(dfp) OVER () - MIN(dfp) OVER(), 0) AS dfp,        
            (atv - min(atv) OVER ()) / NULLIF(MAX(atv) OVER () - MIN(atv) OVER(), 0) AS atv,
            (aiv - min(aiv) OVER ()) / NULLIF(MAX(aiv) OVER () - MIN(aiv) OVER(), 0) AS aiv,
            (adbp - min(adbp) OVER ()) / NULLIF(MAX(adbp) OVER () - MIN(adbp) OVER(), 0) AS adbp                                        
        FROM scaled;
        """)
    
    with psycopg.connect(
        host="127.0.0.1", port=5432, dbname="piscineds", user="luicasad"
    ) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(""" DROP TABLE IF EXISTS user_features;
                                DROP TABLE IF EXISTS user_features_raw;
                                SET work_mem = '512MB';
                                SET max_parallel_workers_per_gather = 0;
                                """)                    
                cur.execute(sql0)     #  calculate frequency
                cur.execute("SELECT * FROM user_features;")

                # retrieve data from query into DataFrame
                rows = cur.fetchall()
                columns = [desc.name for desc in cur.description]

                df = pd.DataFrame(rows, columns=columns)
                features = ["noc", "nos", "ndp", "noi", "tvp", "dlp", "atv", "aiv", "adbp"]
                X = df[features].copy()
                ks = range(1, 11)
                wcss = [KMeans(n_clusters=k, n_init=10, random_state=42).fit(X).inertia_ for k in ks]
                sns.set_theme()  # gray background with white grid, seaborn blue
                plt.plot(ks, wcss)
                plt.xlabel("Number of clusters")
                # plt.ylabel("WCSS (inertia)")
                plt.title("The Elbow Method")
                plt.savefig(carpeta_script /"elbow.png")
                plt.show()


                
            except Exception as e:
                conn.rollback()
                print(f"Error creating elbow chart: {e}")
            finally:
                cur.close()
                conn.commit()
                conn.close()


if __name__ == "__main__":
    num_args = len(sys.argv)
    if num_args == 1:
        main()
    else:
        print("python ./elbow.py")
        sys.exit(1)

