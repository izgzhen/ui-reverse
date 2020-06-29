import sys
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element
import glob
import os
from typing import List, Dict
from termcolor import colored

# Some pre-defined XML constants
ID = '{http://schemas.android.com/apk/res/android}id'
BACKGROUND = '{http://schemas.android.com/apk/res/android}background'
HEIGHT = '{http://schemas.android.com/apk/res/android}layout_height'

jadx_apk_dir = sys.argv[1]
values_dir = jadx_apk_dir + "/resources/res/values/"

# uix: UI hierarchy XML file
uix_path = sys.argv[2]

# resource-id ==> source fragment node
res_id_fragments = {} # type: Dict[str, List[LayoutFragment]]

# fragment node to its parent node
fragment_node_parent = {} # type: Dict[Element, Element]

def get_fragment_node_parents(node: Element):
    """Get the path from node to its parents (until root)
    """
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
        """Initialize a layout fragment node
        id_: resource id
        path: path to the fragment XML that contains the node
        node: the layout source XML node
        """
        self.path = path
        self.id = id_
        self.node = node

def collect_named_fragments(node: Element):
    """Collect all named fragments sub-nodes inside a node"""
    named_fragments = []
    if ID in node.attrib:
        id_ = node.attrib[ID]
        infix = "id/"
        assert infix in id_:
        id_ = id_.split(infix)[1]
        named_fragments.append(LayoutFragment(id_, None, node)) # type: ignore
    for n in node:
        assert n not in fragment_node_parent
        fragment_node_parent[n] = node
        named_fragments.extend(collect_named_fragments(n))
    return named_fragments

def analyze_layout(xml_path: str):
    """Analyze layout XML and map resource id to corresponding source XML node
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    fragments = collect_named_fragments(root)
    for fragment in fragments:
        fragment.path = xml_path
        if fragment.id not in res_id_fragments:
            res_id_fragments[fragment.id] = []
        res_id_fragments[fragment.id].append(fragment)
    layout_name = os.path.basename(xml_path).strip(".xml")

    fragment = LayoutFragment(id_ = layout_name, path = xml_path, node = root)
    if layout_name not in res_id_fragments:
        res_id_fragments[layout_name] = [fragment]
    else:
        res_id_fragments[layout_name].append(fragment)

def get_class(node: Element):
    """Extract class of the element
    Note that if node's class starts with "android.", e.g. "android.widget.TextView",
    it is a system class thus we only takes the last component "TextView" to reduce the
    verbosity
    """
    c = node.attrib["class"]
    if c.startswith("android."):
        return c.split(".")[-1]
    return c

def match_frag(traverse_node, frag_node: Element):
    """Match the class of dynamic vs. static node as a boolean
    traverse_node: LayoutTraverse
    """
    partial_frag_class = frag_node.tag
    traverse_class = traverse_node.node_class
    return partial_frag_class.split(".")[-1] == traverse_class.split(".")[-1]

def match_frag_score(traverse_node, frag_node: Element):
    """Match the class of dynamic vs. static node as a score
    traverse_node: LayoutTraverse
    """
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
        """
        parent: LayoutTraverse
        """
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
            if self.res_id in res_id_fragments:
                fragments = res_id_fragments[self.res_id]
                # Set the list of fragments with correspinding resource ID
                self.fragments = fragments
        self.children = [ LayoutTraverse(n, self) for n in node ]

    def get_parents(self):
        if self.parent is None:
            return []
        return [self.parent] + self.parent.get_parents()

    def traverse_tree_match_frag_score(self, frag_node: Element):
        score = match_frag_score(self, frag_node)
        if list(frag_node) == []:
            return score
        for child in self.children:
            child_score = max(child.traverse_tree_match_frag_score(frag_child)
                                for frag_child in frag_node)
            score += child_score / len(self.children)
        return score

    def solve(self):
        print("\n" + "=" * 120)
        print("Solving for resource-id '%s'" % self.res_id)
        # Print the hierarchy
        self.print()

        # If there is any fragment with same ID
        if self.fragments:
            non_terminal_fragments = []

            # Finding the matched fragment and its similarity score
            parents = self.get_parents()
            for fragment in self.fragments:
                # If the fragment's static XML node has no children (i.e. is a terminal node)
                if len(list(fragment.node)) == 0:
                    frag_parents = get_fragment_node_parents(fragment.node)
                    # If all parents match
                    if all([match_frag(traverse_node, frag_node)
                            for traverse_node, frag_node in zip(parents, frag_parents)]):
                        # Report
                        print("Terminal fragment matched: %s, parents: %s" % (fragment.path, frag_parents))
                # Is a container fragment
                else:
                    # Recursively compute the similarity of its contents
                    score = self.traverse_tree_match_frag_score(fragment.node)
                    non_terminal_fragments.append({
                        "fragment": fragment,
                        "score": score
                    })

            # Report (in order of similarity)
            non_terminal_fragments.sort(key=lambda x:x["score"], reverse=True)
            for item in non_terminal_fragments:
                fragment = item["fragment"]
                score = item["score"]
                print_frag_node_class_tree(fragment.node)
                print("Non-terminal frag: " + fragment.path)
                print("Score: %s" % score)
                print()
        else:
            print("No fragments with such id")

        # Recursive finding
        for c in self.children:
            c.solve()

    def print(self, depth = 0, class_only = False):
        value_str = ""
        if not class_only and self.res_id is not None:
            value_str = ": " + self.res_id
        print("\t|" * depth + "- " + colored(self.node_class, "green") + value_str)
        for child in self.children:
            child.print(depth = depth + 1, class_only = class_only)

def is_potential_layout_xml(xml):
    tree = ET.parse(xml)
    root = tree.getroot()
    if root.tag in ["paths", "menu", "ripple", "vector", "selector", "set", "merge", \
        "translate", "alpha", "layer-list", "inset", "shape", "transition", "bitmap", \
        "animated-vector", "animated-selector", "objectAnimator"]: return False
    if "Layout" in root.tag: return True
    if "View" in root.tag: return True
    if "Button" in root.tag: return True
    if root.tag in ["view", "CheckBox", "Chronometer"]: return True # FIXME: how
    assert False, (root.tag, xml)

if __name__ == "__main__":
    # Construct static fragments nodes
    layout_xmls = glob.glob(jadx_apk_dir + "/resources/res/layout/**/*.xml", recursive=True)
    # FIXME: some APK (9505614c0a9ceb72d6902d8156a940f2c29846a4200f895d6fd7654ec93b3a2d.apk) has obfuscated layout dir name, such as
    #    it is not necessarily /layout
    for xml in glob.glob(jadx_apk_dir + "/resources/res/**/*.xml", recursive=True):
        if xml in layout_xmls: continue
        if "/values" in xml: continue
        if not is_potential_layout_xml(xml): continue
        layout_xmls.append(xml)

    for xml_path in layout_xmls:
        analyze_layout(xml_path)

    # Prepare to analyze the dynamic view hierarchy
    uix_tree = ET.parse(uix_path)
    uix_root = uix_tree.getroot()
    assert uix_root.tag == "hierarchy"
    top_node = list(uix_root)[0]

    traverse = LayoutTraverse(top_node, None)
    traverse.solve()
