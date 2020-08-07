import re
import sys
from typing import Dict
from typing import Tuple

class EventHandlerInfo:
    def __init__(self, java_src, identity, java_line_number,xml_line_number = None, xml_src = None, name=None):
        self.xml_src = xml_src
        self.java_src = java_src
        self.identity = identity
        self.java_line_number = java_line_number
        self.xml_line_number = xml_line_number
        self.name = name

    def toList(self):
        result = []
        result.append("Java Source: " + self.java_src + ":" + self.java_line_number)
        if self.xml_src != None:
            result.append("XML source:" + self.xml_src + ":" + str(self.xml_line_number))
        return result

    def getName(self):
        return self.name


class DialogStruct:
    """
    This is a strucutre handles the dialog information parsed from markii
    """
    def __init__(self, invoke):
        self.invoke = invoke
        self.positive = None
        self.negative = None
        self.neutral = None
        self.title = None
        self.message = None

    def _checkTitle(self, uititle):
        return uititle and self.title and uititle == self.title

    def _checkMessage(self, uiMessage):
        return uiMessage and self.message and uiMessage == self.message


def xmlNumberFinder(identity, path):
    try:
        reader = open(path,'r')
    except OSError:
        print('Path ' + path + ' is not found')
        print('Either the markii temp file is deleted or src_path is wrong')
        sys.exit()

    with reader:
        line = reader.readline()
        cnt = 1
        while line and identity not in line:
            cnt += 1
            line = reader.readline()
        assert(identity in line)
    # Assume the onClick method is below the id
        result = cnt
        while line and 'android:onClick' not in line: #can use methodname as a name too
            result += 1
            line = reader.readline()
        if("onClick" not in line):
            return -1 # instead of crashing, indicate onClick cannot be found
    return result

def getIds(path):
    name2id = {}
    id2name = {}
    with open(path) as reader:
        line = reader.readline()
        while line:
            tmp = re.split(r'\t+', line)
            tmp[1] = tmp[1].replace("\n", "")
            name2id[tmp[0]] = tmp[1]
            id2name[tmp[1]] = tmp[0]
            line = reader.readline()
    return name2id, id2name

def idWrapper(identity):
    return "@+id/" + identity

# add an option to use the temp file
def xmlSrcWrapper(path, src_path):
    loc = path.find('res//')
    return src_path + '/app/src/main/res/' + path[loc + 5:]

def javaSrcWrapper(path):
    path = path.replace('.','/')
    path = 'app/src/main/java/' + path + '.java'
    return path

def readMethodLine(path,id2name, src_path):
    result = {}
    with open(path) as reader:
        line = reader.readline()
        while line:
            tmp = re.split(r'\t+', line)
            tmp[-1] = tmp[-1].replace("\n","")
            result[tmp[-1]] = EventHandlerInfo(java_src=javaSrcWrapper(tmp[-2]),
                                        identity=tmp[-1],
                                        java_line_number=tmp[-3]
                                        )
            if tmp[1] != 'method linked in java':
                if src_path: # want source xml location
                    result[tmp[-1]].xml_src = xmlSrcWrapper(tmp[1], src_path)
                else:
                    result[tmp[-1]].xml_src = tmp[1]
                result[tmp[-1]].xml_line_number = xmlNumberFinder(idWrapper(id2name[tmp[-1]]),
                                                                  result[tmp[-1]].xml_src)
            line = reader.readline()
    return result

def safeParse(src:str):
    try:
        reader = open(src,'r')
    except OSError:
        print('Path ' + src + ' is not found')
        print('Either the markii temp file is deleted or src_path is wrong')
        sys.exit()
    return reader

def parseDialogView(src: str):
    result = {}
    tmpresult: Dict[str, Tuple[DialogStruct, set]] = {}
    reader = safeParse(src)

    with reader:
        line = reader.readline()
        while line:
            if len(line) > 0:
                tmp = re.split(r'\t+', line)
                tmp[1] = tmp[1].replace("\n","")
                if tmp[1] not in tmpresult.keys():
                    tmpresult[tmp[1]] = (DialogStruct(invoke=tmp[1]), set())
                tmpresult[tmp[1]][1].add(tmp[0])
            line = reader.readline()
    for name in tmpresult.keys():
        for id in tmpresult[name][1]:
            result[id] = tmpresult[name][0]
    return result

# parse dialogTitle or dialogMessage, depending on the third parameter passed in
def parseDialogText(src:str, dialogView, title=True):
    reader = safeParse(src)
    with reader:
        line = reader.readline()
        while line:
            if len(line) > 0:
                tmp = re.split(r'\t+', line)
                tmp[1] = tmp[1].replace("\n","")
                if title:
                    dialogView[tmp[1]].title = tmp[0]
                else:
                    dialogView[tmp[1]].message = tmp[0]
            line = reader.readline()


def parseDialogViewButton(src: str, dialogView, id2button):
    reader = safeParse(src)
    line = reader.readline()
    while line:
        if len(line) > 0:
            tmp = re.split(r'\t+', line)
            dialog = dialogView[tmp[0]]

            dialog.positive = id2button.get(tmp[1], None)
            assert(tmp[2] == 'POSITIVE\n')
            line = reader.readline()
            tmp = re.split(r'\t+', line)
            dialog.negative = id2button.get(tmp[1], None)
            assert(tmp[2] == 'NEGATIVE\n')
            line = reader.readline()
            tmp = re.split(r'\t+', line)
            dialog.neutral = id2button.get(tmp[1], None)
            assert(tmp[2] == 'NEUTRAL\n')
        line = reader.readline()


# path passed in is the path to markii results
def getButtonInfo(markii_path, src_path=None):
    name2id, id2name = getIds(markii_path+'idName.facts')
    id2button = readMethodLine(markii_path+'methodLineNumber.facts', id2name, src_path)
    dialogView = parseDialogView(markii_path+'dialogView.facts')
    parseDialogText(markii_path+'dialogTitle.facts', dialogView, title=True)
    parseDialogText(markii_path+'dialogMessage.facts', dialogView, title=False)
    parseDialogViewButton(markii_path+'dialogViewButton.facts', dialogView, id2button)

    result = {}
    for name in name2id.keys():
        if name2id[name] in id2button.keys():
            result[name] = id2button[name2id[name]]
    return result, dialogView
