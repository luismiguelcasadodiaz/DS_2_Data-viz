import psycopg
import sys
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import traceback

carpeta_script = Path(__file__).resolve().parent

feature_name = {
    "noc":"Number of categories",
    "nos":"Number of tickets",
    "ndp":"Number of distinct products",
    "noi":"Number of items purchased",
    "tvp":"Total spent (\u20b3)",
    "dlp":"Days from last purchase",
    "dfp":"Days from first purchase",
    "atv":"Average ticket (\u20b3)",
    "aiv":"Average product value (\u20b3)",
    "adbp":"Average Days between purchase",

}

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

def rescale_centers(centers: np.Array, f1_min, f1_max, f2_min, f2_max):
    raw_centers = []
    c_f1_min = centers[:, 0].min()
    c_f1_rang = centers[:, 0].max() - c_f1_min
    c_f2_min = centers[:, 1].min()    
    c_f2_rang = centers[:, 1].max() - c_f2_min
    f1_rang = f1_max - f1_min
    f2_rang = f2_max - f2_min
    for x, y in centers:
        raw_centers.append(
            [
            f1_min + f1_rang * (c_f1_min - x ) / c_f1_rang,
            f2_min + f2_rang * (c_f2_min - x ) / c_f2_rang
            ]
        )
    return np.array(raw_centers)

def colored_cluster(df: pd.DataFrame, feat, km_feat, centers) -> None:

    fig, ax = plt.subplots(figsize=(10, 8))
    try:
        # Plot points colored by cluster
        #ax.scatter(df.iloc[:, 0],df.iloc[:, 1], c=df.iloc[:, 2], cmap="viridis", s=30, alpha=0.7)
        ax.scatter(df[feat[0]],df[feat[1]], c=df["cluster"], cmap="viridis", s=30, alpha=0.7)

        # Plot centroids
        if feat == km_feat:
            ax.scatter(centers[:, 0], centers[:, 1],
                    c="red", marker="X", s=250, edgecolor="black", label="Centroids")

        ax.set_xlabel(feature_name[feat[0]])
        ax.set_ylabel(feature_name[feat[1]])
        ax.set_title("K-Means Clusters")
        plt.legend()
        plt.savefig(carpeta_script /f"{km_feat[0]}_{km_feat[1]}_col_clu_{feat[0]}_{feat[1]}.png")
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

def hbar(X: pd.Dataframe) -> None:
    k = 4
    colors = plt.cm.viridis(np.linspace(0, 1, k))       # los mismos 4 colores del scatter
    names = {0: "Inactivos", 1:"Nuevos", 2:"Loyal Gold", 3:"Loyal silver"}
    counts = X["cluster"].value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(counts.index.map(names),             # etiquetas con el nombre del grupo
                counts.values,
                color=colors[counts.index])          # color según el número de cluster
    ax.bar_label(bars, padding=3)
    ax.set_xlabel("number of customers")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(carpeta_script /"Cluster_hbars.png")
    plt.show()
    plt.close(fig) 

def RFM(X: pd.DataFrame) -> None:
    names = {0: "Inactivos", 1:"Nuevos", 2:"Loyal Gold", 3:"Loyal silver"}
    axis = X.aggregate({"dlp":["min", "max"], "nos":["min", "max"]})
    clusters = X.groupby("cluster").aggregate({"dlp": "mean","nos":"mean","tvp":"mean"})
    clusters["name"] = clusters.index.map(names)
    fig, ax = plt.subplots(figsize=(10, 5))
    scatter = ax.scatter(
        x=clusters["dlp"] / 30, 
        y=clusters["nos"],
        s=clusters["tvp"],
        c=clusters.index,
        cmap="viridis")
    ax.set_xlim(axis.loc["min","dlp"] /30 , axis.loc["max","dlp"] /30 )
    ax.set_ylim(axis.loc["min","nos"], axis.loc["max","nos"])
    ax.set_xlabel("Median recency (month)")
    ax.set_ylabel("Median frecuency")    
    ax.spines[["top", "right"]].set_visible(False)
    for x, y, etiqueta, M in zip(clusters["dlp"], clusters["nos"], clusters["name"], clusters["tvp"]):
        ax.annotate(
            f'Average "{etiqueta}": {M:.2f} \u20b3',
            (x/30, y),
            textcoords="offset points",
            xytext=(0.7 * M/100, 0.5 * M/60),     # desplazamiento en puntos para no tapar el marcador
            fontsize=8,
        )
    plt.tight_layout()
    plt.savefig(carpeta_script /"RFM.png")
    plt.show()
    plt.close(fig)

    

def main(km_feat1: str, km_feat2: str )-> None:
    features_all =["noc", "nos", "ndp", "noi", "tvp", "dlp", "dfp", "atv", "aiv", "adbp"]
    assert km_feat1 in features_all, f"The feature {km_feat1} is not in the dataset"
    assert km_feat2 in features_all, f"The feature {km_feat2} is not in the dataset"
    km_features =[km_feat1, km_feat2]
    with psycopg.connect(
            host="127.0.0.1", port=5432, dbname="piscineds", user="luicasad"
        ) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("""SELECT * FROM user_features_raw""")
                    rows = cur.fetchall()
                    columns = [desc.name for desc in cur.description]

                    X = pd.DataFrame(rows, columns=columns)
                    X = X.apply(pd.to_numeric)   #  SQL NUMERIC values arribe as object
                    scaler = StandardScaler().set_output(transform="pandas")
                    X_scaled = scaler.fit_transform(X[km_features])
                    #correlation(X[features_all])

                    #cur.execute("""SELECT * FROM user_features_raw""")
                    #rows = cur.fetchall()
                    #columns = [desc.name for desc in cur.description]

                    #raw = pd.DataFrame(rows, columns=columns)

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
                    labels = km.fit_predict(X_scaled)
                    centers = scaler.inverse_transform(km.cluster_centers_)
                    X["cluster"] = labels
                    #raw["cluster"] = labels
                    print(centers)
                    #for i, feat1 in enumerate(features_all):
                    #    for feat2 in features_all[i + 1 :]:
                    #        if feat1 != feat2:
                    #            colored_cluster(raw, [feat1, feat2], km_features, centers)
                    hbar(X)
                    RFM(X)
                    colored_cluster(X, km_features, km_features, centers)
                    #pca(X, centers)

                except Exception as e:
                    conn.rollback()
                    print(f"Error creating Cluster chart: {e}")
                    traceback.print_exc()
                finally:
                    cur.close()
                    conn.close()

                    


if __name__ == "__main__":
    num_args = len(sys.argv)
    if num_args == 3:
        main(sys.argv[1], sys.argv[2])
    else:
        print("python ./clustering.py FEAT1=nos FEAT2=dfp")
        sys.exit(1)