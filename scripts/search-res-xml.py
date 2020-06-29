import sys
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element
import glob
import os
from typing import List, Dict
from termcolor import colored

ID = '{http://schemas.android.com/apk/res/android}id'
BACKGROUND = '{http://schemas.android.com/apk/res/android}background'
HEIGHT = '{http://schemas.android.com/apk/res/android}layout_height'

jadx_apk_dir = sys.argv[1]
layout_dir = jadx_apk_dir + "/resources/res/layout/"
values_dir = layout_dir.replace("/layout", "/values")

uix_path = sys.argv[2]
uix_tree = ET.parse(uix_path)

res_id_paths = {} # type: Dict[str, List[LayoutFragment]]

fragment_node_parent = {} # type: Dict[Element, Element]

def get_fragment_node_parents(node: Element):
    if node not in fragment_node_parent:
        return []
    p = fragment_node_parent[node]
    return [p] + get_fragment_node_parents(p)

def print_frag_node_class_tree(node: Element, depth = 0):
    print("\t|" * depth + "- " + colored(node.tag, "green"))
    for child in node:
        print_frag_node_class_tree(child, depth = depth + 1)

class LayoutFragment(object):
    def __init__(self, id_: str, path: str, node: Element):
        self.path = path
        self.id = id_
        self.node = node

def collect_named_fragments(node: Element):
    named_fragments = []
    if ID in node.attrib:
        id_ = node.attrib[ID]
        prefix = "@+id/"
        if id_.startswith(prefix):
            id_ = id_[len(prefix):]
            named_fragments.append(LayoutFragment(id_, None, node)) # type: ignore
        else:
            print("WRAN: unknown prefix " + id_)
    for n in node:
        assert n not in fragment_node_parent
        fragment_node_parent[n] = node
        named_fragments.extend(collect_named_fragments(n))
    return named_fragments

def analyze_layout(xml_path: str):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    fragments = collect_named_fragments(root)
    for fragment in fragments:
        fragment.path = xml_path
        if fragment.id not in res_id_paths:
            res_id_paths[fragment.id] = []
        res_id_paths[fragment.id].append(fragment)
    layout_name = os.path.basename(xml_path).strip(".xml")

    fragment = LayoutFragment(id_ = layout_name, path = xml_path, node = root)
    if layout_name not in res_id_paths:
        res_id_paths[layout_name] = [fragment]
    else:
        res_id_paths[layout_name].append(fragment)

for xml_path in glob.glob(layout_dir + "/**/*.xml", recursive=True):
    analyze_layout(xml_path)

def get_class(node: Element):
    c = node.attrib["class"]
    if c.startswith("android"):
        return c.split(".")[-1]
    return c

def traverse_match_frag(traverse_node, frag_node: Element):
    partial_frag_class = frag_node.tag
    traverse_class = traverse_node.node_class
    return partial_frag_class.split(".")[-1] == traverse_class.split(".")[-1]

def traverse_match_frag_score(traverse_node, frag_node: Element):
    partial_frag_class = frag_node.tag
    traverse_class = traverse_node.node_class
    n1 = partial_frag_class.split(".")[-1]
    n2 = traverse_class.split(".")[-1]
    if traverse_class == partial_frag_class:
        return 1.0
    elif n1 == n2:
        return 0.8
    elif n1 in n2 or n2 in n1:
        return 0.5
    return 0.2

class LayoutTraverse(object):
    def __init__(self, node: Element, parent):
        self.parent = parent
        self.fragments = None
        self.node = node
        self.res_id = None
        self.node_class = get_class(self.node)
        if node.attrib["resource-id"] != "":
            pkg_prefix = node.attrib["package"] + ":id/"
            if node.attrib["resource-id"].startswith(pkg_prefix):
                self.res_id = node.attrib["resource-id"][len(pkg_prefix):]
            elif node.attrib["resource-id"].startswith("android:id/"):
                self.res_id = node.attrib["resource-id"][len("android:id/"):]
            else:
                raise Exception(f"Unexpected node: {node}")
            if self.res_id in res_id_paths:
                fragments = res_id_paths[self.res_id]
                self.fragments = fragments
        self.children = [ LayoutTraverse(n, self) for n in node ]

    def get_parents(self):
        if self.parent is None:
            return []
        return [self.parent] + self.parent.get_parents()

    def traverse_tree_match_frag_score(self, frag_node: Element):
        score = traverse_match_frag_score(self, frag_node)
        if list(frag_node) == []:
            return score
        for child in self.children:
            child_score = max(child.traverse_tree_match_frag_score(frag_child)
                                for frag_child in frag_node)
            score += child_score / len(self.children)
        return score

    def solve(self):
        print("Solve %s" % self.res_id)
        self.print(class_only=True)
        parents = self.get_parents()
        if self.fragments:
            non_empty_fragments = []
            for fragment in self.fragments:
                if len(list(fragment.node)) == 0:
                    frag_parents = get_fragment_node_parents(fragment.node)
                    if all([traverse_match_frag(traverse_node, frag_node)
                            for traverse_node, frag_node in zip(parents, frag_parents)]):
                        print("Empty fragment matched: %s, parents: %s" % (fragment.path, frag_parents))
                else:
                    score = self.traverse_tree_match_frag_score(fragment.node)
                    non_empty_fragments.append({
                        "fragment": fragment,
                        "score": score
                    })

            non_empty_fragments.sort(key=lambda x:x["score"], reverse=True)
            for item in non_empty_fragments:
                fragment = item["fragment"]
                score = item["score"]
                print_frag_node_class_tree(fragment.node)
                print("Non-empty frag: " + fragment.path)
                print("Score: %s" % score)
                print()
        print()
        for c in self.children:
            c.solve()
        print()

    def print(self, depth = 0, class_only = False):
        value_str = ""
        if not class_only and self.res_id is not None:
            value_str = ": " + self.res_id
        print("\t|" * depth + "- " + colored(self.node_class, "green") + value_str)
        for child in self.children:
            child.print(depth = depth + 1, class_only = class_only)

uix_root = uix_tree.getroot()
assert uix_root.tag == "hierarchy"
top_node = list(uix_root)[0]

traverse = LayoutTraverse(top_node, None)
print("Solving...")
traverse.solve()
traverse.print()
