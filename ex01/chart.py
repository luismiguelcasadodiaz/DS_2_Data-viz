import psycopg
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import traceback

def purch_cust_on_time(df: pd.DataFrame)-> None:
    print(df)
    fig, ax = plt.subplots()
    # plt.figure(figsize=(7, 7))
    ax.plot(df["day"],df["num_customers"])
    plt.title("Customers by day")
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonthday=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    ax.set_ylabel("Number of customers")
    fig.savefig("purch_cust_on_time.png")
    plt.show()

def sales_cust_on_time(df: pd.DataFrame)-> None:
    print(df)
    fig, ax = plt.subplots()
    # plt.figure(figsize=(7, 7))

    ax.bar(df["month"].dt.strftime("%b"),df["month_sales"]/1_000_000)
    plt.title("Sales by month")
    #ax.xaxis.set_major_locator(mdates.MonthLocator(bymonthday=1))
    #ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    ax.set_ylabel("Total sales in million of \u20b3")
    fig.savefig("sales_cust_on_time.png")
    plt.show()    
def avera_cust_on_time(df: pd.DataFrame)-> None:
    print(df)
    fig, ax = plt.subplots()
    # plt.figure(figsize=(7, 7))
    min_value = df["average_sales_by_customer"] - df["average_sales_by_customer"]
    ax.fill_between(df["day"],min_value, df["average_sales_by_customer"])
    plt.title("Average sales by customer by day")
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonthday=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    ax.set_ylabel("Average spend/customers in \u20b3")
    fig.savefig("avera_cust_on_time.png")
    plt.show()

sql0_0 = psycopg.sql.SQL("""
    SELECT EXISTS (SELECT 1 FROM pg_matviews 
    WHERE matviewname = 'purch_cust_on_time');
    """)
sql1_0 = psycopg.sql.SQL("""
    SET work_mem = '512MB';
    SET max_parallel_workers_per_gather = 0;

    CREATE MATERIALIZED VIEW IF NOT EXISTS purch_cust_on_time AS
    SELECT event_time::date as day, count(*) AS num_customers
    FROM customers        
    WHERE event_type = 'purchase'
    GROUP BY 1
    ORDER BY 1;
    """)
sql2_0 = psycopg.sql.SQL("""
    SELECT day, num_customers FROM purch_cust_on_time;
    """)
sql3_0 = psycopg.sql.SQL("REFRESH MATERIALIZED VIEW purch_cust_on_time;")               


sql0_1 = psycopg.sql.SQL("""
    SELECT EXISTS (SELECT 1 FROM pg_matviews 
    WHERE matviewname = 'sales_cust_on_time');
    """)
sql1_1 = psycopg.sql.SQL("""
    SET work_mem = '512MB';
    SET max_parallel_workers_per_gather = 0;

    CREATE MATERIALIZED VIEW IF NOT EXISTS sales_cust_on_time AS
    SELECT DATE_TRUNC('month', event_time) as month, sum(price) AS month_sales
    FROM customers
    WHERE event_type = 'purchase'
    GROUP BY DATE_TRUNC('month', event_time)
    ORDER BY 1;
    """)
sql2_1 = psycopg.sql.SQL("""
    SELECT month, month_sales FROM sales_cust_on_time;
    """)
sql3_1 = psycopg.sql.SQL("REFRESH MATERIALIZED VIEW ales_cust_on_time;")               


sql0_2 = psycopg.sql.SQL("""
    SELECT EXISTS (SELECT 1 FROM pg_matviews 
    WHERE matviewname = 'avera_cust_on_time');
    """)
sql1_2 = psycopg.sql.SQL("""
    SET work_mem = '512MB';
    SET max_parallel_workers_per_gather = 0;

    CREATE MATERIALIZED VIEW IF NOT EXISTS avera_cust_on_time AS
    SELECT  
        day, 
        day_sales / day_customers as average_sales_by_customer 
    FROM (
            SELECT 
                day, 
                sum(cust_day_purchase) as day_sales,
                count(*) as day_customers
            FROM (
                    SELECT 
                        event_time::date AS day,
                        user_id AS customer,
                        sum(price) AS cust_day_purchase
                    FROM customers 
                    WHERE event_type = 'purchase'
                    GROUP BY 1, 2
                )
            GROUP BY 1
            ORDER BY 1
        );
    """)
sql2_2 = psycopg.sql.SQL("""
    SELECT day, average_sales_by_customer  FROM avera_cust_on_time;
    """)
sql3_2 = psycopg.sql.SQL("REFRESH MATERIALIZED VIEW avera_cust_on_time;")            
charts = {
    'purch_cust_on_time':([sql0_0, sql1_0, sql2_0, sql3_0],purch_cust_on_time),
    'sales_cust_on_time':([sql0_1, sql1_1, sql2_1, sql3_1],sales_cust_on_time),
    'avera_cust_on_time':([sql0_2, sql1_2, sql2_2, sql3_2],avera_cust_on_time),
}
def main(refresh: bool):
    
    with psycopg.connect(
        host="127.0.0.1", port=5432, dbname="piscineds", user="luicasad"
    ) as conn:
        with conn.cursor() as cur:
            for k, (queries, chart) in charts.items():
                try:
                    cur.execute(queries[0])     #  Check existence
                    exists = cur.fetchone()[0]
                    if not exists:
                        print(f"Creating view {k}")
                        cur.execute(queries[1]) #  View creation
                        print(f"Retriving data for {k}")
                        cur.execute(queries[2]) #  Retrieve data
                    elif refresh:
                        print(f"Refreshing view {k}")
                        cur.execute(queries[3]) #  Refresh view
                        print(f"Retriving data for {k}")
                        cur.execute(queries[2]) #  Retrieve data
                    else:
                        print(f"Retriving data for {k}")
                        cur.execute(queries[2]) #  Retrieve data

                    # retrieve data from query into DataFrame
                    rows = cur.fetchall()
                    columns = [desc.name for desc in cur.description]
                    df = pd.DataFrame(rows, columns=columns)
                    chart(df)
                except Exception as e:
                    conn.rollback()
                    print(f"Error creating {k} chart from evet_types: {e}")
                    traceback.print_exc()

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
