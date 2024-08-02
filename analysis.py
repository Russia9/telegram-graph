import pandas as pd
from pyvis.network import Network
import networkx as nx

relations = pd.read_csv("assets/telegram-graph.relations.csv", sep=",", header=None)
channels = pd.read_csv("assets/telegram-graph.channels.csv", sep=",", header=None)

net = Network(notebook=True, cdn_resources="remote",
              bgcolor="#222222",
              font_color="white",
              height="1200px",
              width="100%",
              )

i = 0
for channel in channels.iterrows():
    if i == 0:
        i += 1
        continue

    try:
        size = int(channel[1][4]) / 1000
    except:
        size = 1

    if size < 1:
        size = 1

    # print(channel)
    # print(channel[1][1], channel[1][2], size)
    net.add_node(channel[1][1], label=channel[1][2], size=size)

i = 0
edge_weights = {}
url_nodes = {}
for relation in relations.iterrows():
    if i == 0:
        i += 1
        continue

    try:
        edge_weights[(relation[1][1], relation[1][5])] += 1
    except:
        if relation[1][4] == "url":
            url_nodes[relation[1][5]] = True

        edge_weights[(relation[1][1], relation[1][5])] = 1

for node in url_nodes:
    net.add_node(node, label=node, size=10, color="#2b964b")

for edge in edge_weights:
    try:
        net.add_edge(edge[0], edge[1], value=edge_weights[edge])
    except Exception as e:
        print(e)

net.show("assets/telegram-graph.html")
