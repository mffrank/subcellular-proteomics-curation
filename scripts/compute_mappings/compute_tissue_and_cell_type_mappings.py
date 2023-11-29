#!/usr/bin/env python
# coding: utf-8
# flake8: noqa

# # Ancestor and Descendant Mappings for Tissues and Cell Types
#
# ## Overview
#
# The ontology-aware tissue and cell type filters in the Single Cell Data Portal each require two artifacts generated by this notebook:
#
# #### 1. Ancestor Mappings
# To facilitate result set filtering, datasets must be tagged with the set of ancestors for each tissue and cell type value associated with it. For example, if a dataset is tagged with the tissue `lung`, all ancestors of `lung` must be added to the dataset's `tissue_ancestors` value.
#
# This notebook generates a dictionary of ancestors keyed by either a tissue or cell type ontology term ID. The dictionary is copied to the Single Cell Data Portal's `tissue_ontology_mappings` or `cell_type_ontology_mappings` constants (see [/utils/ontology_mappings/constants.py](https://github.com/chanzuckerberg/single-cell-data-portal/tree/main/backend/common/utils/ontology_mappings/constants.py)) and the backend then joins datasets and their ancestor mappings on request of the `datasets/index` API endpoint.
#
# The ancestor mappings should be updated when:
#
# 1. The ontology version is updated, or,
# 2. A new tissue or cell type is added to the production corpus.
#
# #### 2. Descendant Mappings
# To facilitate in-filter, cross-panel restriction of filter values, a descendant hierarchy dictionary is required by the Single Cell Data Portal frontend. For example, if a user selects `hematopoietic system` in the tissue filter's `System` panel, the values in the tissue filter's `Organ` and `Tissue` panels must be restricted by `hematopoietic system`.
#
# This notebook generates a dictionary of descendants keyed by tissue or cell type ontology term ID. The dictionary is copied to the Single Cell Data Portal's frontend constants `TISSUE_DESCENDANTS` or `CELL_TYPE_DESCENDANTS` (see [constants.ts](https://github.com/chanzuckerberg/single-cell-data-portal/blob/main/frontend/src/components/common/Filter/common/constants.ts)).
#
# The descendant mappings should be updated when:
#
# 1. The ontology version is updated,
# 2. A new tissue or cell type is added to the production corpus, or,
# 3. The hand-curated systems, organs, cell classes or cell subclasses are updated.
#
# ## Notebook Implementation Notes
#
# ### Tissues
# This notebook extracts a subgraph of UBERON starting with a set of hand-curated systems. Specifically, this notebook:
#
# 1. Loads the required ontology file, pinned for 2.0.0 schema.
# 2. Builds descendants of all systems and orphans (i.e. tissues in production that have no corresponding system), traversing both `is_a` and `part_of` relationships.
#
# From the subgraph, the two artifacts described above can then be generated:
#
# 1. Build an ancestor dictionary
#     - Maps every tissue in the production corpus to their ancestors.
#     - Writes the dictionary to a JSON file, to be copied into `tissue_ontology_mapping` in the Single Cell Data Portal.
#
# 2. Build a descendant dictionary
#     - Builds a dictionary, mapping every tissue in the production corpus to their descendants. Descendants are limited to the set of tissues lower in the tissue hierarchy than themselves. For example, systems can have organ or tissue descendants, organs can have tissue descendants and tissues can have no descendants.
#     - Writes the dictionary to a JSON file, to be copied into `TISSUE_DESCENDANTS` in the Single Cell Data Portal.
#
# #### Hand-Curation of Systems and Organs
# Systems and organs were hand-curated in this [spreadsheet](https://docs.google.com/spreadsheets/d/18761SLamZUN9FLAMV_zmg0lutSSUkArCEs8GnprxtZE/edit#gid=717648045).
#
# ### Cell Types
# This notebook extracts a subgraph of CL starting with a set of hand-curated cell classes. Specifically, this notebook:
#
# 1. Loads the required ontology file, pinned for 2.0.0 schema.
# 2. Builds descendants of all cell classes and orphans (i.e. cell types in production that have no corresponding cell class), traversing only `is_a` relationships.
#
# From the subgraph, the two artifacts described above can then be generated:
#
# 1. Build an ancestor dictionary
#     - Maps every cell type in the production corpus to their ancestors.
#     - Writes the dictionary to a JSON file, to be copied into `cell_type_ontology_mapping` in the Single Cell Data Portal.
#
# 2. Build a descendant dictionary
#     - Builds a dictionary, mapping every cell type in the production corpus to their descendants. Descendants are limited to the set of cell types lower in the cell type hierarchy than themselves. For example, cell classes can have cell subclass or cell type descendants, cell subclasses can have cell type descendants and call types can have no descendants.
#     - Writes the dictionary to a JSON file, to be copied into `TISSUE_DESCENDANTS` in the Single Cell Data Portal.
#
# #### Hand-Curation of Cell Classes and Cell Subclasses
# Cell classes and cell subclasses were hand-curated in this [spreadsheet](https://docs.google.com/spreadsheets/d/1ebGc-LgZJhNsKinzQZ3rpzuh1e1reSH3Rcbn88mCOaU/edit#gid=1625183014).
#
# ## Running the Notebook
# This notebook is optimized to be run within vscode's notebook runner on a developer local workstation in the context of the single-cell-data-portal Git repository.
#
# ### Prerequisites
# 1. This version of the notebook was setup and last run with Monterey 12.6.1
# 1. Python 3.10 >= installed and activated in a virtual environment.
# 1. `brew install graphviz`

# In[1]:


import json

import pygraphviz as pgv
import requests
import yaml
from owlready2 import World


# In[2]:


# Load owl.info to grab latest ontology sources
owl_info_yml = "cellxgene_schema_cli/cellxgene_schema/ontology_files/owl_info.yml"
with open(owl_info_yml, "r") as owl_info_handle:
    owl_info = yaml.safe_load(owl_info_handle)


# In[3]:


# Load CL, pinned for 3.0.0 schema.
cl_latest_key = owl_info["CL"]["latest"]
cl_ontology = owl_info["CL"]["urls"][cl_latest_key]
cl_world = World()
cl_world.get_ontology(cl_ontology).load()


# In[4]:


# Load UBERON
uberon_latest_key = owl_info["UBERON"]["latest"]
uberon_ontology = owl_info["UBERON"]["urls"][uberon_latest_key]
uberon_world = World()
uberon_world.get_ontology(uberon_ontology).load()


# #### Tissue Constants

# In[5]:


# Hand-curated systems.
system_tissues = [
    "UBERON_0001017",
    "UBERON_0004535",
    "UBERON_0001009",
    "UBERON_0001007",
    "UBERON_0000922",
    "UBERON_0000949",
    "UBERON_0002330",
    "UBERON_0002390",
    "UBERON_0002405",
    "UBERON_0000383",
    "UBERON_0001016",
    "UBERON_0000010",
    "UBERON_0001008",
    "UBERON_0000990",
    "UBERON_0001004",
    "UBERON_0001032",
    "UBERON_0001434",
]


# In[6]:


# Hand-curated organs.
organ_tissues = [
    "UBERON_0000992",
    "UBERON_0000029",
    "UBERON_0002048",
    "UBERON_0002110",
    "UBERON_0001043",
    "UBERON_0003889",
    "UBERON_0018707",
    "UBERON_0000178",
    "UBERON_0002371",
    "UBERON_0000955",
    "UBERON_0000310",
    "UBERON_0000970",
    "UBERON_0000948",
    "UBERON_0000160",
    "UBERON_0002113",
    "UBERON_0002107",
    "UBERON_0000004",
    "UBERON_0001264",
    "UBERON_0001987",
    "UBERON_0002097",
    "UBERON_0002240",
    "UBERON_0002106",
    "UBERON_0000945",
    "UBERON_0002370",
    "UBERON_0002046",
    "UBERON_0001723",
    "UBERON_0000995",
    "UBERON_0001013",
]


# In[7]:


# Production tissues with no corresponding hand-curated system; required so
# that they are explicitly added to the generated subgraph.
orphan_tissues = [
    "UBERON_0001013",  # adipose tissue
    "UBERON_0009472",  # 	axilla
    "UBERON_0018707",  # bladder organ
    "UBERON_0000310",  # breast
    "UBERON_0001348",  # brown adipose
    "UBERON_0007106",  # 	chorionic villus
    "UBERON_0000030",  # 	lamina propria
    "UBERON_0015143",  # mesenteric fat pad
    "UBERON_0000344",  # mucosa
    "UBERON_0003688",  # 	omentum
    "UBERON_0001264",  # pancreas
    "UBERON_0000175",  # 	pleural effusion
    "UBERON_0000403",  # scalp
    "UBERON_0001836",  # 	saliva
    "UBERON_0001416",  # skin of abdomen
    "UBERON_0002097",  # skin of body
    "UBERON_0001868",  # skin of chest
    "UBERON_0001511",  # skin of leg
    "UBERON_0002190",  # subcutaneous adipose tissue
    "UBERON_0002100",  # trunk
    "UBERON_0035328",  # upper outer quadrant of breast
    "UBERON_0001040",  # yolk sac
    "UBERON_0000014",  # zone of skin
]


# #### Cell Type Constants

# In[8]:


# Hand-curated cell classes.
cell_classes = [
    "CL_0002494",  # cardiocyte
    "CL_0002320",  # connective tissue cell
    "CL_0000473",  # defensive cell
    "CL_0000066",  # epithelial cell
    "CL_0000988",  # hematopoietic cell
    "CL_0002319",  # neural cell
    "CL_0011115",  # precursor cell
    "CL_0000151",  # secretory cell
    "CL_0000039",  # germ cell line
    "CL_0000064",  # ciliated cell
    "CL_0000183",  # contractile cell
    "CL_0000188",  # cell of skeletal muscle
    "CL_0000219",  # motile cell
    "CL_0000325",  # stuff accumulating cell
    "CL_0000349",  # extraembryonic cell
    "CL_0000586",  # germ cell
    "CL_0000630",  # supporting cell
    "CL_0001035",  # bone cell
    "CL_0001061",  # abnormal cell
    "CL_0002321",  # embryonic cell (metazoa)
    "CL_0009010",  # transit amplifying cell
    "CL_1000600",  # lower urinary tract cell
    "CL_4033054",  # perivascular cell
]


# In[9]:


# Hand-curated cell subclasses.
cell_subclasses = [
    "CL_0000624",  # CD4-positive, alpha-beta T cell
    "CL_0000625",  # CD8-positive, alpha-beta T cell
    "CL_0000084",  # T cell
    "CL_0000236",  # B cell
    "CL_0000451",  # dendritic cell
    "CL_0000576",  # monocyte
    "CL_0000235",  # macrophage
    "CL_0000542",  # lymphocyte
    "CL_0000738",  # leukocyte
    "CL_0000763",  # myeloid cell
    "CL_0008001",  # hematopoietic precursor cell
    "CL_0000234",  # phagocyte
    "CL_0000679",  # glutamatergic neuron
    "CL_0000617",  # GABAergic neuron
    "CL_0000099",  # interneuron
    "CL_0000125",  # glial cell
    "CL_0000101",  # sensory neuron
    "CL_0000100",  # motor neuron
    "CL_0000117",  # CNS neuron (sensu Vertebrata)
    "CL_0000540",  # neuron
    "CL_0000669",  # pericyte
    "CL_0000499",  # stromal cell
    "CL_0000057",  # fibroblast
    "CL_0000152",  # exocrine cell
    "CL_0000163",  # endocrine cell
    "CL_0000115",  # endothelial cell
    "CL_0002076",  # endo-epithelial cell
    "CL_0002078",  # meso-epithelial cell
    "CL_0011026",  # progenitor cell
    "CL_0000015",  # male germ cell
    "CL_0000021",  # female germ cell
    "CL_0000034",  # stem cell
    "CL_0000055",  # non-terminally differentiated cell
    "CL_0000068",  # duct epithelial cell
    "CL_0000075",  # columnar/cuboidal epithelial cell
    "CL_0000076",  # squamous epithelial cell
    "CL_0000079",  # stratified epithelial cell
    "CL_0000082",  # epithelial cell of lung
    "CL_0000083",  # epithelial cell of pancreas
    "CL_0000095",  # neuron associated cell
    "CL_0000098",  # sensory epithelial cell
    "CL_0000136",  # fat cell
    "CL_0000147",  # pigment cell
    "CL_0000150",  # glandular epithelial cell
    "CL_0000159",  # seromucus secreting cell
    "CL_0000182",  # hepatocyte
    "CL_0000186",  # myofibroblast cell
    "CL_0000187",  # muscle cell
    "CL_0000221",  # ectodermal cell
    "CL_0000222",  # mesodermal cell
    "CL_0000244",  # urothelial cell
    "CL_0000351",  # trophoblast cell
    "CL_0000584",  # enterocyte
    "CL_0000586",  # germ cell
    "CL_0000670",  # primordial germ cell
    "CL_0000680",  # muscle precursor cell
    "CL_0001063",  # neoplastic cell
    "CL_0002077",  # ecto-epithelial cell
    "CL_0002222",  # vertebrate lens cell
    "CL_0002327",  # mammary gland epithelial cell
    "CL_0002503",  # adventitial cell
    "CL_0002518",  # kidney epithelial cell
    "CL_0002535",  # epithelial cell of cervix
    "CL_0002536",  # epithelial cell of amnion
    "CL_0005006",  # ionocyte
    "CL_0008019",  # mesenchymal cell
    "CL_0008034",  # mural cell
    "CL_0009010",  # transit amplifying cell
    "CL_1000296",  # epithelial cell of urethra
    "CL_1000497",  # kidney cell
    "CL_2000004",  # pituitary gland cell
    "CL_2000064",  # ovarian surface epithelial cell
    "CL_4030031",  # interstitial cell
]


# In[10]:


# Production cell types with no corresponding hand-curated cell class; required
# so that they are explicitly added to the generated subgraph.
orphan_cell_types = [
    "CL_0000003",
    "CL_0009012",
    "CL_0000064",
    "CL_0000548",
    "CL_0000677",
    "CL_0000186",
    "CL_0009011",
    "CL_1001319",
    "CL_0000188",
    "CL_1000497",
    "CL_0008019",
    "CL_1000597",
    "CL_1000500",
    "CL_1000271",
    "CL_0000663",
    "CL_0000255",
    "CL_0001034",
    "CL_0001063",
    "CL_0011101",
    "CL_0008036",
    "CL_0000525",
    "CL_0002488",
    "CL_0000148",
    "CL_0001064",
    "CL_0002092",
    "CL_0002371",
    "CL_0009005",
    "CL_0000019",
    "CL_0000114",
    "CL_0000630",
    "CL_0008034",
    "CL_0000010",
    "CL_0009002",
    "CL_0000670",
    "CL_0000222",
    "CL_0009010",
    "CL_0000001",
    "CL_0000183",
    "CL_1000458",
    "CL_2000021",
    "CL_0001061",
]


# #### Function Definitions

# In[11]:


def build_descendants_graph(entity_name, graph):  # type: ignore
    """
    Recursively build set of descendants (that is, is_a descendants) for the
    given entity and add to graph.
    """

    # Add node to graph, this covers the case where a top-level tissue has no
    # children.
    graph.add_node(entity_name)

    # List descendants via is_a relationship.
    subtypes = list_direct_descendants(entity_name)  # type: ignore

    for subtype in subtypes:
        child_name = subtype.name

        # Check if child has been added to graph already.
        child_visted = graph.has_node(child_name)

        # Add valid child to graph as a descendant.
        graph.add_edge(entity_name, child_name)

        # Build graph for child if it hasn't already been visited.
        if not child_visted:
            build_descendants_graph(child_name, graph)  # type: ignore


# In[12]:


def build_descendants_and_parts_graph(entity_name, graph):  # type: ignore
    """
    Recursively build set of descendants and parts (that is, include both is_a
    and part_of descendants) for the given entity and add to graph.
    """

    # Add node to graph, this covers the case where a top-level tissue has no
    # children.
    graph.add_node(entity_name)

    # List descendants via is_a and part_of relationships.
    subtypes_and_parts = list_direct_descendants_and_parts(entity_name)  # type: ignore

    for subtype_or_part in subtypes_and_parts:
        # Each child should be a singleton array; detect, report and continue if
        # an invalid child is found (manual investigation of failure is required).
        child_len = len(subtype_or_part)
        if child_len == 0 or child_len > 1:
            print("Invalid child length - please investigate: ", child_len, subtype_or_part)
            continue

        child = subtype_or_part[0]

        # Ignore axioms, only add true entities.
        if not is_axiom(child):  # type: ignore
            child_name = child.name

            # Ignore disjoint.
            if child_name == "Nothing":
                continue

            # Check if child has been added to graph already.
            child_visted = graph.has_node(child_name)

            # Add valid child to graph as a descendant.
            graph.add_edge(entity_name, child_name)

            # Build graph for child if it hasn't already been visited.
            if not child_visted:
                build_descendants_and_parts_graph(child_name, graph)  # type: ignore


# In[13]:


def build_graph_for_cell_types(entity_names):  # type: ignore
    """
    Extract a subgraph of CL for the given cell types.
    """
    graph = pgv.AGraph()
    for entity_name in entity_names:
        build_descendants_graph(entity_name, graph)  # type: ignore
    return graph


# In[14]:


def build_graph_for_tissues(entity_names):  # type: ignore
    """
    Extract a subgraph of UBERON for the given tissues.
    """
    tissue_graph = pgv.AGraph()
    for entity_name in entity_names:
        build_descendants_and_parts_graph(entity_name, tissue_graph)  # type: ignore
    return tissue_graph


# In[15]:


def is_axiom(entity):  # type: ignore
    """
    Returns true if the given entity is an axiom.
    For example, obo.UBERON_0001213 & obo.BFO_0000050.some(obo.NCBITaxon_9606)
    """
    return hasattr(entity, "Classes")


# In[16]:


def is_cell_culture(entity_name):  # type: ignore
    """
    Returns true if the given entity name contains (cell culture).
    """
    return "(cell culture)" in entity_name


# In[17]:


def is_cell_culture_or_organoid(entity_name):  # type: ignore
    """
    Returns true if the given entity name contains (cell culture) or (organoid).
    """
    return is_cell_culture(entity_name) or is_organoid(entity_name)  # type: ignore


# In[18]:


def is_organoid(entity_name):  # type: ignore
    """
    Returns true if the given entity name contains "(organoid)".
    """
    return "(organoid)" in entity_name


# In[19]:


def key_ancestors_by_entity(entity_names, graph):  # type: ignore
    """
    Build a dictionary of ancestors keyed by entity for the given entities.
    """

    ancestors_by_entity = {}
    for entity_name in entity_names:
        descendants = set()  # type: ignore
        list_ancestors(entity_name, graph, descendants)  # type: ignore

        sanitized_entity_name = reformat_ontology_term_id(entity_name, to_writable=True)
        sanitized_ancestors = [reformat_ontology_term_id(descendant, to_writable=True) for descendant in descendants]

        ancestors_by_entity[sanitized_entity_name] = sanitized_ancestors

    return ancestors_by_entity


# In[20]:


def key_organoids_by_ontology_term_id(entity_names):  # type: ignore
    """
    Returns a dictionary of organoid ontology term IDs by stem ontology term ID.
    """

    organoids_by_ontology_term_id = {}
    for entity_name in entity_names:
        if is_organoid(entity_name):  # type: ignore
            ontology_term_id = entity_name.replace(" (organoid)", "")
            organoids_by_ontology_term_id[ontology_term_id] = entity_name

    return organoids_by_ontology_term_id


# In[21]:


def list_ancestors(entity_name, graph, ancestor_set):  # type: ignore
    """
    From the given graph, recursively build up set of ancestors for the given
    entity.
    """

    ancestor_set.add(entity_name)

    # Ignore cell culture and organoids
    if is_cell_culture_or_organoid(entity_name):  # type: ignore
        return ancestor_set

    try:
        ancestor_entities = graph.predecessors(entity_name)
    except KeyError:
        # Detect, report and continue if entity not found in graph. Manual
        # investigation of failure is required.
        print(f"{entity_name} not found - either add a parent to this entity or add this entity to the orphans list.")
        return ancestor_set

    for ancestor_entity in ancestor_entities:
        list_ancestors(ancestor_entity, graph, ancestor_set)  # type: ignore

    return ancestor_set


# In[22]:


def list_descendants(entity_name, graph, all_successors):  # type: ignore
    """
    From the given graph, recursively build up set of descendants for the given
    entity from the given
    """

    # Ignore cell culture and organoid tissues.
    if is_cell_culture(entity_name) or is_organoid(entity_name):  # type: ignore
        return

    successors = []
    try:
        successors = graph.successors(entity_name)
    except KeyError:
        # Detect, report and continue if entity not found in graph. Manual
        # investigation of failure is required.
        print(f"{entity_name} not found - please investigate.")

    # Add descendants to the set.
    if len(successors):
        all_successors.update(successors)

    # Find descendants of children of entity.
    for successor in successors:
        list_descendants(successor, graph, all_successors)  # type: ignore


# In[23]:


def list_direct_descendants(entity_name):  # type: ignore
    """
    Return the set of descendants for the given entity.
    """

    entity = cl_world.search_one(iri=f"http://purl.obolibrary.org/obo/{entity_name}")
    if not entity:
        print(f"{entity_name} not found in the ontology - please investigate.")
        return []

    return entity.subclasses()


# In[24]:


def list_direct_descendants_and_parts(entity_name):  # type: ignore
    """
    Determine the set of descendants and parts for the given entity.

    Tissues descendants must be traversed through both is_a and part_of
    relationships. For example, "retina" is_a "photoceptor array" whereas
    "photoceptor array" is part_of "eye". To build the full list of descendants
    for eye, both is_a and part_of relationships must be examined.

    WHERE
    --
    Looks for entities that are a subclass of the restriction (anonymous class)
    where the definition of the restriction set is: has some members (part_of)
    of the given entity. See https://www.cs.vu.nl/~guus/public/owl-restrictions/.

    ?class rdfs:subClassOf <http://purl.obolibrary.org/obo/{entity}>
    --
    Looks for direct descendants (is_a).
    """

    query = """
    SELECT ?class 
    WHERE {{
      {{
        ?class rdfs:subClassOf ?restriction .
        ?restriction owl:onProperty <http://purl.obolibrary.org/obo/BFO_0000050> .
        ?restriction owl:someValuesFrom <http://purl.obolibrary.org/obo/{entity}> .
      }}

    UNION {{
      ?class rdfs:subClassOf <http://purl.obolibrary.org/obo/{entity}>
      }}
    }}
    """.format(
        entity=entity_name
    )
    classes = uberon_world.sparql(query)
    return classes


# In[25]:


def reformat_ontology_term_id(ontology_term_id: str, to_writable: bool = True):  # type: ignore
    """
    Converts ontology term id string between two formats:
        - `to_writable == True`: from "UBERON_0002048" to "UBERON:0002048"
        - `to_writable == False`: from "UBERON:0002048" to "UBERON_0002048"
    """

    if to_writable:
        if ontology_term_id.count("_") != 1:
            raise ValueError(f"{ontology_term_id} is an invalid ontology term id, it must contain exactly one '_'")
        return ontology_term_id.replace("_", ":")
    else:
        if ontology_term_id.count(":") != 1:
            raise ValueError(f"{ontology_term_id} is an invalid ontology term id, it must contain exactly one ':'")
        return ontology_term_id.replace(":", "_")


# In[26]:


def write_ancestors_by_entity(entities, graph, file_name):  # type: ignore
    """
    Create dictionary of ancestors keyed by entity and write to file. The
    contents of the generated file is copied into ${entity}_ontology_mapping.py
    in the single-cell-data-portal repository and is used to key datasets with
    their corresponding entity ancestors.
    """
    ancestors_by_entity = key_ancestors_by_entity(entities, graph)  # type: ignore
    with open(file_name, "w") as f:
        json.dump(ancestors_by_entity, f)


# In[27]:


def write_descendants_by_entity(entity_hierarchy, graph, file_name):  # type: ignore
    """
    Create descendant relationships between the given entity hierarchy.
    """
    all_descendants = {}
    for idx, entity_set in enumerate(entity_hierarchy):
        # Create the set of descendants that can be included for this entity set.
        # For example, systems can include organs or tissues,
        # organs can only include tissues, tissues can't have descendants.
        accept_lists = entity_hierarchy[idx + 1 :]

        # Tissue or cell type for example will not have any descendants.
        if not accept_lists:
            continue

        accept_list = [i for sublist in accept_lists for i in sublist]
        organoids_by_ontology_term_id = key_organoids_by_ontology_term_id(accept_list)  # type: ignore

        # List descendants of entity in this set.
        for entity_anme in entity_set:
            descendants = set()  # type: ignore
            list_descendants(entity_anme, graph, descendants)  # type: ignore

            # Determine the set of descendants that be included.
            descendant_accept_list = []
            for descendant in descendants:
                # Include all entities in the accept list.
                if descendant in accept_list:
                    descendant_accept_list.append(descendant)

                # Add organoid descendants, if any.
                if descendant in organoids_by_ontology_term_id:
                    descendant_accept_list.append(organoids_by_ontology_term_id[descendant])

            # Add organoid entity, if any.
            if entity_anme in organoids_by_ontology_term_id:
                descendant_accept_list.append(organoids_by_ontology_term_id[entity_anme])

            if not descendant_accept_list:
                continue

            # Add descendants to dictionary.
            sanitized_entity_name = reformat_ontology_term_id(entity_anme, to_writable=True)
            sanitized_descendants = [
                reformat_ontology_term_id(descendant, to_writable=True) for descendant in descendant_accept_list
            ]
            all_descendants[sanitized_entity_name] = sanitized_descendants

    with open(file_name, "w") as f:
        json.dump(all_descendants, f)


# #### Calculate Tissue Graph and Tissue Ancestor and Descendant Mappings

# In[28]:


# Load latest prod tissues and cell types


response = requests.get("https://api.cellxgene.cziscience.com/dp/v1/datasets/index")
datasets = json.loads(response.text)
prodTissueSet = set()
prodCellTypeSet = set()
for dataset in datasets:
    for tissue in dataset["tissue"]:
        prodTissueSet.add(reformat_ontology_term_id(tissue["ontology_term_id"], False))
    for cellType in dataset["cell_type"]:
        prodCellTypeSet.add(reformat_ontology_term_id(cellType["ontology_term_id"], False))

prod_tissues = list(prodTissueSet)
prod_cell_types = list(prodCellTypeSet)
print(len(prod_tissues), " prod tissues found")
print(len(prod_cell_types), " prod cell types found")


# In[29]:


# Extract a subgraph from UBERON for the hand-curated systems and orphans,
# collapsing is_a and part_of relations.
tissue_graph = build_graph_for_tissues(system_tissues + orphan_tissues)  # type: ignore


# In[30]:


# Create ancestors file, the contents of which are to be copied to
# tissue_ontology_mapping.py and read by Single Cell Data Portal BE.
write_ancestors_by_entity(prod_tissues, tissue_graph, "scripts/compute_mappings/tissue_ontology_mapping.json")  # type: ignore


# In[31]:


# Create descendants file, the contents of which are to be copied to
# TISSUE_DESCENDANTS and read by Single Cell Data Portal FE.
tissue_hierarchy = [system_tissues, organ_tissues, prod_tissues]
write_descendants_by_entity(tissue_hierarchy, tissue_graph, "scripts/compute_mappings/tissue_descendants.json")  # type: ignore


# #### Calculate Cell Type Graph and Cell Type Ancestor and Descendant Mappings

# In[32]:


# Extract a subgraph from CL for the hand-curated cell classes and orphans,
# including only is_a relationships.
cell_type_graph = build_graph_for_cell_types(cell_classes + orphan_cell_types)  # type: ignore


# In[33]:


# Create ancestors file, the contents of which will be loaded into
# cell_type_ontology_mapping and read by Single Cell Data Portal BE.
write_ancestors_by_entity(  # type: ignore
    prod_cell_types,
    cell_type_graph,
    "scripts/compute_mappings/cell_type_ontology_mapping.json",
)


# In[34]:


# Create descendants file, the contents of which are to be copied to
# CELL_TYPE_DESCENDANTS and read by Single Cell Data Portal FE.
cell_type_hierarchy = [cell_classes, cell_subclasses, prod_cell_types]
write_descendants_by_entity(cell_type_hierarchy, cell_type_graph, "scripts/compute_mappings/cell_type_descendants.json")  # type: ignore
