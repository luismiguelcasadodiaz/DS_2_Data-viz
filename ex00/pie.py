import psycopg
import sys
import pandas as pd
import matplotlib.pyplot as plt


def main(refresh: bool):

    sql0 = psycopg.sql.SQL("""
        SELECT EXISTS (SELECT 1 FROM pg_matviews 
        WHERE matviewname = 'event_type_counts');
        """)
    sql1 = psycopg.sql.SQL("""
        SET work_mem = '512MB';
        SET max_parallel_workers_per_gather = 0;

        CREATE MATERIALIZED VIEW IF NOT EXISTS event_type_counts AS
        SELECT event_type, count(*) AS customers
        FROM customers
         GROUP BY 1;
        """)

    sql2 = psycopg.sql.SQL("""
        SELECT event_type, customers FROM event_type_counts ORDER BY 2;
        """)
    sql3 = psycopg.sql.SQL("REFRESH MATERIALIZED VIEW event_type_counts;")

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
                df = pd.DataFrame(rows, columns=columns)
                print(df)

                plt.figure(figsize=(7, 7))
                plt.pie(df["customers"], labels=df["event_type"], autopct="%1.1f%%", startangle=90)
                plt.title("Event type's distribution")
                plt.axis("equal")
                plt.savefig("pie.png")
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
        print("python ./pie.py")
        sys.exit(1)
