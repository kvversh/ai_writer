import json
import os
from datetime import datetime
import networkx as nx


class StoryOntology:
    """
    Онтологическая память рассказа.
    Хранит:
    - Узлы (персонажи, объекты, локации)
    - Связи между ними
    - Пространственные отношения
    - Скрытый слой (подтекст, известный только Архитектору)
    - Таймлайн событий (Event Sourcing)
    """

    def __init__(self, story_id: str = "default"):
        self.story_id = story_id
        self.graph = nx.DiGraph()
        self.timeline = []
        self.hidden_layer = {}
        self.metadata = {
            "genre": "",
            "theme": "",
            "created_at": datetime.now().isoformat(),
        }
        self._storage_dir = "./story_storage"
        os.makedirs(self._storage_dir, exist_ok=True)

    def add_character(self, name: str, traits: dict, hidden_traits: dict = None):
        self.graph.add_node(name, type="character", **traits)
        if hidden_traits:
            self.hidden_layer[name] = hidden_traits

    def add_object(self, name: str, properties: dict):
        self.graph.add_node(name, type="object", **properties)

    def add_location(self, name: str, description: str):
        self.graph.add_node(name, type="location", description=description)

    def add_relation(self, source: str, target: str, relation: str):
        self.graph.add_edge(source, target, relation=relation)

    def add_spatial_relation(self, subject: str, relation: str, object_name: str):
        """
        Добавить пространственное отношение.
        Примеры:
        - add_spatial_relation("Барсик", "внутри", "лоток")
        - add_spatial_relation("лоток", "рядом с", "Ослик")
        """
        self.graph.add_edge(subject, object_name, relation=f"spatial:{relation}")

    def get_spatial_context(self, entity: str) -> list:
        """Получить все пространственные отношения для сущности."""
        relations = []
        for u, v, data in self.graph.edges(data=True):
            if data.get("relation", "").startswith("spatial:"):
                rel_type = data["relation"].replace("spatial:", "")
                if u == entity:
                    relations.append(f"{entity} {rel_type} {v}")
                elif v == entity:
                    relations.append(f"{u} {rel_type} {entity}")
        return relations

    def check_spatial_consistency(self) -> list:
        """Проверить онтологию на пространственные противоречия."""
        issues = []
        for node in self.graph.nodes():
            inside = []
            near = []
            on = []
            for u, v, data in self.graph.edges(data=True):
                rel = data.get("relation", "")
                if not rel.startswith("spatial:"):
                    continue
                rel_type = rel.replace("spatial:", "")
                if u == node:
                    if rel_type == "внутри":
                        inside.append(v)
                    elif rel_type == "рядом с":
                        near.append(v)
                    elif rel_type == "на":
                        on.append(v)
            # Проверка противоречий
            for obj in inside:
                if obj in near:
                    issues.append(f"{node} одновременно 'внутри' и 'рядом с' {obj}")
                if obj in on:
                    issues.append(f"{node} одновременно 'внутри' и 'на' {obj}")
            for obj in on:
                if obj in near:
                    issues.append(f"{node} одновременно 'на' и 'рядом с' {obj}")
        return issues

    def update_node(self, node: str, **kwargs):
        if node in self.graph:
            self.graph.nodes[node].update(kwargs)

    def record_event(self, event: dict):
        event["timestamp"] = len(self.timeline)
        event["time"] = datetime.now().isoformat()
        self.timeline.append(event)
        if "node_changes" in event:
            for node, changes in event["node_changes"].items():
                if node in self.graph:
                    self.graph.nodes[node].update(changes)

    def get_snapshot(self, node: str) -> dict:
        if node not in self.graph:
            return {}
        return {"id": node, **self.graph.nodes[node]}

    def get_hidden(self, node: str) -> dict:
        return self.hidden_layer.get(node, {})

    def get_scene_context(self, location: str = None) -> dict:
        context = {"characters": [], "objects": [], "locations": [], "relations": [], "spatial": []}
        for node, data in self.graph.nodes(data=True):
            node_type = data.get("type", "unknown")
            if node_type == "character":
                visible = {k: v for k, v in data.items() if k != "type"}
                context["characters"].append({"name": node, **visible})
            elif node_type == "object":
                context["objects"].append({"name": node, **{k: v for k, v in data.items() if k != "type"}})
            elif node_type == "location":
                context["locations"].append({"name": node, "description": data.get("description", "")})
        for u, v, data in self.graph.edges(data=True):
            rel = data.get("relation", "")
            if rel.startswith("spatial:"):
                context["spatial"].append({"from": u, "to": v, "relation": rel.replace("spatial:", "")})
            else:
                context["relations"].append({"from": u, "to": v, "relation": rel})
        context["recent_events"] = self.timeline[-5:] if self.timeline else []
        return context

    def get_architect_context(self) -> dict:
        context = self.get_scene_context()
        context["hidden_layer"] = self.hidden_layer
        context["full_timeline"] = self.timeline
        return context

    def validate_consistency(self) -> list:
        issues = []
        for node, data in self.graph.nodes(data=True):
            if data.get("type") == "character" and "location" not in data:
                issues.append(f"Персонаж {node} не имеет локации")
        issues.extend(self.check_spatial_consistency())
        return issues

    def save(self):
        data = {
            "story_id": self.story_id,
            "graph": nx.node_link_data(self.graph),
            "timeline": self.timeline,
            "hidden_layer": self.hidden_layer,
            "metadata": self.metadata,
        }
        path = os.path.join(self._storage_dir, f"{self.story_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self):
        path = os.path.join(self._storage_dir, f"{self.story_id}.json")
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.graph = nx.node_link_graph(data["graph"])
        self.timeline = data["timeline"]
        self.hidden_layer = data["hidden_layer"]
        self.metadata = data["metadata"]
        return True