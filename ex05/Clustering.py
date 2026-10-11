import psycopg
import sys
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans

carpeta_script = Path(__file__).resolve().parent

def main()-> None:
    with psycopg.connect(
            host="127.0.0.1", port=5432, dbname="piscineds", user="luicasad"
        ) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("""SELECT * FROM user_features""")
                    rows = cur.fetchall()
                    columns = [desc.name for desc in cur.description]

                    X = pd.DataFrame(rows, columns=columns)

                    cur.execute("""SELECT * FROM user_features_raw""")
                    rows = cur.fetchall()
                    columns = [desc.name for desc in cur.description]

                    raw = pd.DataFrame(rows, columns=columns)

                    


if __name__ == "__main__":
    main()
