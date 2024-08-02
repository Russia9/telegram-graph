import pandas as pd
from pyvis.network import Network

data = pd.read_csv("assets/1night.relations.csv", sep=",", header=None)
data.columns = ["channel_id", "source"]
sample = data.sample(1000, random_state=1)
sample.head(10)

net = Network(notebook=True, cdn_resources="remote",
              bgcolor="#222222",
              font_color="white",
              height="750px",
              width="100%",
              )
nodes = list(set([*sample.channel_id, *sample.source]))
edges = sample.values.tolist()
net.add_nodes(nodes)
net.add_edges(edges)
net.show("graph.html")
