import psycopg
import sys
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

carpeta_script = Path(__file__).resolve().parent

def correlation(df:pd.DataFrame) -> None:
    corr = df.corr(numeric_only=True)
    fig, ax = plt.subplots(figsize=(10, 8))
    try:
        sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm",
                    vmin=-1, vmax=1, center=0, square=True,
                    linewidths=0.5, ax=ax)
        ax.set_title("Feature Correlation Heatmap")
        fig.tight_layout()
        plt.savefig(carpeta_script /"Correlation_heatmap.png")
        plt.show()
    finally:
        plt.close(fig)   # frees the figure even if something above fails
    
def colored_cluster(df: pd.DataFrame, centers) -> None:

    fig, ax = plt.subplots(figsize=(10, 8))
    try:
        # Plot points colored by cluster
        ax.scatter(df.iloc[:, 0],df.iloc[:, 1], c=df.iloc[:, 2], cmap="viridis", s=30, alpha=0.7)

        # Plot centroids
        ax.scatter(centers[:, 0], centers[:, 1],
                    c="red", marker="X", s=250, edgecolor="black", label="Centroids")

        ax.set_xlabel(df.columns[0])
        ax.set_ylabel(df.columns[1])
        ax.set_title("K-Means Clusters")
        plt.legend()
        plt.savefig(carpeta_script /"colored_cluster.png")
        plt.show()
    finally:
        plt.close(fig)   # frees the figure even if something above fails   


def pca(df: pd.DataFrame, centers) -> None:
    #Reduce to 2D for visualization
    pca = PCA(n_components=2)
    X_2d = pca.fit_transform(df)
    centers_2d = pca.transform(centers)

    plt.scatter(X_2d[:, 0], X_2d[:, 1], c=labels, cmap="viridis", s=30, alpha=0.7)
    plt.scatter(centers_2d[:, 0], centers_2d[:, 1],
                c="red", marker="X", s=250, edgecolor="black", label="Centroids")
    plt.xlabel("PC 1")
    plt.ylabel("PC 2")
    plt.title("K-Means Clusters (PCA projection)")
    plt.legend()
    plt.savefig(carpeta_script /"Cluster1.png")
    plt.show()

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
                    X = X.apply(pd.to_numeric)   #  SQL NUMERIC values arribe as object
                    features =["noc", "nos", "ndp", "noi", "tvp", "dlp", "dfp", "atv", "aiv", "adbp"]
                    #correlation(X[features])

                    cur.execute("""SELECT * FROM user_features_raw""")
                    rows = cur.fetchall()
                    columns = [desc.name for desc in cur.description]

                    raw = pd.DataFrame(rows, columns=columns)

                    km =KMeans(
                        n_clusters=4, 
                        init="k-means++",   #  Picks startign point spread far apart
                        n_init=10,          #  Reruns 10 times, Keep best result.
                        max_iter=310,       #  Iterations to stop if not convergence
                        tol=1e-4,           #  Stops if centroid moves less than tolerance
                        verbose=1,          #  Assistance for debuggin
                        random_state=42,    #  Allows reproductibel results.
                    )
                    
                    # correlation(X[features])
                    features =["nos", "dfp"]
                    labels = km.fit_predict(X[features])
                    centers = km.cluster_centers_
                    X["cluster"] = labels
                    raw["cluster"] = labels
                    features.append("cluster")
                    print(centers)
                    colored_cluster(X[features], centers)
                    #pca(X, centers)

                except Exception as e:
                    conn.rollback()
                    print(f"Error creating Cluster chart: {e}")
                finally:
                    cur.close()
                    conn.close()

                    


if __name__ == "__main__":
    main()
