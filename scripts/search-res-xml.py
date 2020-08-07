from abstract_widget import EventHandlerInfo
from abstract_widget import DialogStruct
from typing import Dict
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element
import glob
import os
from typing import List, Dict
from termcolor import colored
import abstract_widget
import argparse
from msbase.subprocess_ import try_call_std # pylint: disable=import-error
from msbase.utils import getenv # pylint: disable=import-error
import json

# Some pre-defined XML constants
ID = '{http://schemas.android.com/apk/res/android}id'
BACKGROUND = '{http://schemas.android.com/apk/res/android}background'
HEIGHT = '{http://schemas.android.com/apk/res/android}layout_height'

parser = argparse.ArgumentParser(description='UI-reverse tool')

parser.add_argument('--jadx_file_dir',
                    type=str,
                    default="/tmp/jadx",
                    help='directory stores jadx files')

parser.add_argument('--uix_path',
                    type=str,
                    default="/tmp/uix.xml",
                    help='path to uix')

parser.add_argument('--apk',
                    type=str,
                    required = True,
                    help='path to apk')

parser.add_argument('--src_path',
                    type=str,
                    help='src loc, if src path is not passed in, returns the temp xml method line ')

parser.add_argument('--markii_file_loc',
                    type = str,
                    default="/tmp/markii/",
                    help='path to markii genareted files')

parser.add_argument("--run_markii",
                type = str,
                default="T",
                help='run markii or not')

parser.add_argument("--run_jadx",
                type = str,
                default="T",
                help='run markii or not')

args = parser.parse_args()
if args.run_markii=='T':
    MARKII_DIR = getenv("MARKII")

def run_markii(apk: str, facts_dir: str, delete_temp: str):
    """
    Depends on Scala SBT by default
    """
    os.system("mkdir -p " + facts_dir)
    # Run markii
    try_call_std(["bash", MARKII_DIR + "/build-run-markii.sh", apk, facts_dir, delete_temp], output=True, timeout_s=1200)

def run_jadx(apk:str, jadx:str):
    try_call_std(["bash",'jadx',apk, '-d',jadx])

delete_temp = 'T'
if args.src_path == None:
    delete_temp = 'F'
if args.run_markii == 'T':
    run_markii(args.apk, args.markii_file_loc, delete_temp)
if args.run_jadx == 'T':
    run_jadx(args.apk, args.jadx_file_dir)

jadx_apk_dir = args.jadx_file_dir
values_dir = jadx_apk_dir + "/resources/res/values/"

# uix: UI hierarchy XML file
uix_path = args.uix_path

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

class DialogUI(object):
    def __init__(self, message:str, title:str, positive:EventHandlerInfo,\
                 negative:EventHandlerInfo, neutral:EventHandlerInfo,\
                 button1:str, button2:str, button3:str):
        self.message = message
        self.title = title
        self.positive = positive
        self.negative = negative
        self.neutral = neutral
        self.button1 = button1
        self.button2 = button2
        self.button3 = button3

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
        assert infix in id_
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

def d(o):
        if hasattr(o, '__dict__'):
            return o.__dict__
        else:
            return "<Omitted for Circular Reference>"

class SuitableJsonObj:
    def __init__(self, handlerMap=None, dialogInfo=None, fragments=None, res_id=None, \
                node_class=None, depth=None, children=None, values_str=None, methodLineInfo=None):
                self.handlerMap = dict(handlerMap)
                self.dialogInfo = dict(dialogInfo)
                self.fragments=self.fragmentsParser(fragments)
                self.res_id=res_id
                self.depth=depth
                self.node_class=node_class
                self.children=[c.jsonObj for c in children]
                self.values_str=values_str
                self.methodLineInfo = methodLineInfo

    def fragmentsParser(self, fragments):
        result = []
        if not fragments:
            return None
        for f in fragments:
            d = {}
            d["id"] = f.id
            d["path"] = f.path
            result.append(d)
        return result

    def toJSON(self):
        return json.dumps(self, default=lambda o: d(o), sort_keys=True, indent=4)

def fillDialogInfo(markiiDialog:DialogStruct, ui:DialogUI):
    if markiiDialog._checkTitle(ui.title) or markiiDialog._checkMessage(ui.message):
        assert(ui.positive == None and ui.negative == None and ui.neutral == None)
        ui.positive = markiiDialog.positive
        ui.negative = markiiDialog.negative
        ui.neutral = markiiDialog.neutral

class LayoutTraverse(object):

    def setSuperDialogChildren(self, superDialog):
            self.dialog = superDialog
            for child in self.children:
                child.setSuperDialogChildren(superDialog)

    def findNode(self, root, targetClass, targetId):
        for item in root.children:
            if item.node_class == targetClass and item.res_id == targetId:
                return item
        return None

    def getDialogLLC(self):
        """
        This is a naive structure that handles information of androidx.appcompat.widget.LinearLayoutCompat
        (the structure contains the dialog window)parsed from uiXML (the snapshot).
        """

        """
        We determine an LLC is a dialog if:
            There is a LinearLayout contains an title_template
            There is a FrameLayout contains a TextView called message
            There is a ScrollView called buttonPanel
        """
        LinearLayout = self.findNode(self, "LinearLayout", "topPanel")
        if not LinearLayout:
            return False
        LinearLayout = self.findNode(LinearLayout, "LinearLayout", "title_template")
        if not LinearLayout:
            return False
        TextView = self.findNode(LinearLayout, "TextView","alertTitle")
        if not TextView:
            return False
        title = TextView.text

        FrameLayout = self.findNode(self.node, "FrameLayout", "contentPanel")
        if not FrameLayout:
            return False
        ScrollView = self.findNode(FrameLayout, "ScrollView", "scrollView")
        if not ScrollView:
            return False
        LinearLayout = self.findNode(ScrollView, "LinearLayout", None)
        if not LinearLayout:
            return False
        TextView = self.findNode(LinearLayout, "TextView", "message")
        message = TextView.text

        ScrollView = self.findNode(self.node, "ScrollView", "buttonPanel")
        if not ScrollView:
            return False
        LinearLayout = self.findNode(ScrollView, "LinearLayout", None)
        if not LinearLayout:
            return False
        button1, button2, button3 = None, None, None
        for button in LinearLayout:
            if "button1" in button.value_str:
                button1 = button.text
            elif "button2" in button.value_str:
                button2 = button.text
            elif "button3" in button.value_str:
                button3 = button.text
        if button1 and button2 and button3 and title and message:
            return DialogUI(message, title, None, None, None, button1, button2, button3)
        else:
            return None

    def getDialogLL(self):
        LinearLayout = self.findNode(self, "LinearLayout", "parentPanel")
        if not LinearLayout:
            return False
        FrameLayout = self.findNode(LinearLayout, "FrameLayout", "contentPanel")
        if not FrameLayout:
            return False
        ScrollView = self.findNode(FrameLayout, "ScrollView", "scrollView")
        if not ScrollView:
            return False
        __LinearLayout = self.findNode(ScrollView, "LinearLayout", None)
        if not __LinearLayout:
            return False
        TextView = self.findNode(__LinearLayout, "TextView", "message")
        if not TextView:
            return False

        message = TextView.text

        '''
        TODO:
        subject to change, there may be title and no message
        '''

        ButtonPanel = self.findNode(LinearLayout, "ScrollView", "buttonPanel")
        if not ButtonPanel:
            return False
        LinearLayout = self.findNode(ButtonPanel, "LinearLayout", None)
        if not LinearLayout:
            return False

        button1, button2, button3 = None, None, None
        for button in LinearLayout.children:
            if "button1" in button.value_str:
                button1 = button.text
            elif "button2" in button.value_str:
                button2 = button.text
            elif "button3" in button.value_str:
                button3 = button.text
        if button1 or button2 or button3 or message:
            return DialogUI(message, None, None, None, None, button1, button2, button3)
        else:
            return None

    def getDialog(self):
        ans = self.getDialogLL()
        if not ans:
            ans = self.getDialogLLC()
        return ans

    def __init__(self, node: Element, parent, depth=0, superDialog=None):
        """
        parent: LayoutTraverse
        """
        self.node = node
        self.parent = parent
        self.fragments = None
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
        self.depth = depth
        self.value_str = ""
        if self.res_id is not None:
            self.value_str = ": " + self.res_id
        self.methodLineInfo = None
        self.text = self.node.attrib['text']
        if self.res_id in handlerMap.keys():
            self.methodLineInfo = handlerMap[self.res_id].toList()

        # set children
        self.children = [ LayoutTraverse(n, self, depth=self.depth + 1, superDialog=superDialog) for n in node ]

        # pattern recognization
        self.dialog = superDialog
        if not self.dialog:
            if self.node_class == "LinearLayoutCompat" or self.node_class == "FrameLayout":
                self.dialog = self.getDialog()
                if self.dialog:
                    # find the dialog info from markii
                    for dialog_markii in set(dialogInfo.values()):
                        fillDialogInfo(dialog_markii, self.dialog)
            # set superDialog forall children
            if self.dialog:
                self.setSuperDialogChildren(self.dialog)

        self.jsonObj = SuitableJsonObj(handlerMap=handlerMap, dialogInfo=dialogInfo,\
                                       fragments=self.fragments, res_id=self.res_id, \
                                       node_class=self.node_class, depth=self.depth, \
                                       children=self.children, values_str=self.value_str,\
                                       methodLineInfo=self.methodLineInfo)

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

    def solve(self, json_output):
        print("\n" + "=" * 120)
        print("Solving for resource-id '%s'" % self.res_id)
        self.print(print_depth = 0)
        y = self.jsonObj.toJSON()
        json_output.append(y)

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
            c.solve(json_output)

    def print(self, print_depth = 0, class_only = False):
        print("\t|" * print_depth + "- " + colored(self.node_class, "green") + self.value_str)
        if self.dialog and "button1" in self.value_str:
            for line in self.dialog.positive.toList():
                print("\t|" * (print_depth + 1) + "- " + colored(line, "red") )
            # print("\t|" * (print_depth + 1) + "- " + colored(str(self.dialog.positive), "red") )
        elif self.dialog and "button2" in self.value_str:
            for line in self.dialog.negative.toList():
                print("\t|" * (print_depth + 1) + "- " + colored(line, "red") )
            # print("\t|" * (print_depth + 1) + "- " + colored(str(self.dialog.negative), "red") )
        elif self.dialog and "button3" in self.value_str:
            # print("\t|" * (print_depth + 1) + "- " + colored(str(self.dialog.neutral), "red") )
            for line in self.dialog.neutral.toList():
                print("\t|" * (print_depth + 1) + "- " + colored(line, "red") )
        elif self.methodLineInfo:
            for line in self.methodLineInfo:
                print("\t|" * (print_depth + 1) + "- " + colored(line, "red") )
        for child in self.children:
            child.print(print_depth = print_depth + 1, class_only = class_only)

def is_potential_layout_xml(xml):
    """
    Guess whether `xml` is a layout XML file using some very limited heuristics.
    """
    tree = ET.parse(xml)
    root = tree.getroot()
    # NOTE: this is a empirical list -- please update it manually if the exception is thrown
    # by creating a pull request
    if root.tag in ["paths", "menu", "ripple", "vector", "selector", "set", "merge", \
        "translate", "alpha", "layer-list", "inset", "shape", "transition", "bitmap", \
        "animated-vector", "animated-selector", "objectAnimator"]: return False
    # If the XML tag satisfies the following conditions, we guess it is a Layout XML.
    if "Layout" in root.tag: return True
    if "View" in root.tag: return True
    if "Button" in root.tag: return True
    if root.tag in ["view", "CheckBox", "Chronometer"]: return True # FIXME: how
    raise Exception("Unexpected tag %s from %s" % (root.tag, xml))

if __name__ == "__main__":
    # Construct static fragments nodes
    layout_xmls = glob.glob(jadx_apk_dir + "/resources/res/layout/**/*.xml", recursive=True)
    if layout_xmls == []:
        # FIXME: some APK (9505614c0a9ceb72d6902d8156a940f2c29846a4200f895d6fd7654ec93b3a2d.apk) has obfuscated layout dir name, such as
        #    it is not necessarily /layout
        for xml in glob.glob(jadx_apk_dir + "/resources/res/**/*.xml", recursive=True):
            if xml in layout_xmls: continue
            if "/values" in xml: continue
            if not is_potential_layout_xml(xml): continue
            layout_xmls.append(xml)

    for xml_path in layout_xmls:
        analyze_layout(xml_path)
    if not os.path.exists('/tmp/ui-reverse/'):
        os.makedirs('/tmp/ui-reverse/')
    f=open('/tmp/ui-reverse/output.json','w')
    f.close()

    # Prepare to analyze the dynamic view hierarchy
    uix_tree = ET.parse(uix_path)
    uix_root = uix_tree.getroot()
    assert uix_root.tag == "hierarchy"
    top_node = list(uix_root)[0]
    handlerMap, dialogInfo = abstract_widget.getButtonInfo(args.markii_file_loc, src_path = args.src_path)
    traverse = LayoutTraverse(top_node, None)
    json_output: List[str] = []
    traverse.solve(json_output)

    with open('/tmp/ui-reverse/output.json','w') as f:
        json.dump(json_output, f)
    f.close()

