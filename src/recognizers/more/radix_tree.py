# radix tree
# some strings
import json
from operator import index

premiere_string = "adobe"
deuxieme_string = 'added'
troiseieme_string = "allan"
quatriem_string = "adore"

# trés manual but work with me now
settet: set[str] = set()
settet.add(premiere_string)
settet.add(deuxieme_string)
settet.add(troiseieme_string)
settet.add(quatriem_string)

print(settet)

def build_trie(words: set[str]):

    trie = {}

    for word in words:

        print(f"adding {word} to the trie")
        node = trie
        for char in word:
            if char not in node:
                node[char] = {}
            node = node[char]
        node["$"] = True

    return trie

trie = build_trie(settet)

print(trie)

def compress_node(node: dict):

    new_node = {}

    for char, child in node.items():

        if char == "$":
            new_node["$"] = True
            continue

        label = char
        current = child

        while "$" not in current and len(current) == 1:
            next_char, next_child = next(iter(current.items()))
            label = label + next_char
            current = next_child

        new_node[label] = compress_node(current)

    return new_node

def build_radix_trie(words: set[str]):

    trie = {}

    for word in words:

        print(f"adding {word} to the radix tree hehe not trie")
        node = trie
        for char in word:
            print(node)
            if char not in node:
                node[char] = {}
            node = node[char]
        node["$"] = True

    trie = compress_node(trie)

    return trie

radix_trie = build_radix_trie(settet)
jsoned = json.dumps(radix_trie, indent=2) # just cleany ready

print(radix_trie)
print(jsoned)