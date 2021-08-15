"""strata.py: RESQML stratigraphy classes."""

version = '15th August 2021'

import logging

log = logging.getLogger(__name__)
log.debug('strata.py version ' + version)

import warnings

import resqpy.organize as rqo
import resqpy.weights_and_measures as wam
import resqpy.olio.xml_et as rqet
import resqpy.olio.uuid as bu
from resqpy.olio.xml_namespaces import curly_namespace as ns
from resqpy.olio.base import BaseResqpy

valid_compositions = [
   'intrusive clay ', 'intrusive clay', 'organic', 'intrusive mud ', 'intrusive mud', 'evaporite salt',
   'evaporite non salt', 'sedimentary siliclastic', 'carbonate', 'magmatic intrusive granitoid',
   'magmatic intrusive pyroclastic', 'magmatic extrusive lava flow', 'other chemichal rock', 'sedimentary turbidite'
]

valid_implacements = ['autochtonous', 'allochtonous']

valid_domains = ('depth', 'time', 'mixed')

valid_deposition_modes = [
   'proportional between top and bottom', 'parallel to bottom', 'parallel to top', 'parallel to another boundary'
]

valid_ordering_criteria = ['age', 'apparent depth', 'measured depth']  # stratigraphic column must be ordered by age

valid_contact_relationships = [
   'frontier feature to frontier feature', 'genetic boundary to frontier feature',
   'genetic boundary to genetic boundary', 'genetic boundary to tectonic boundary',
   'stratigraphic unit to frontier feature', 'stratigraphic unit to stratigraphic unit',
   'tectonic boundary to frontier feature', 'tectonic boundary to genetic boundary',
   'tectonic boundary to tectonic boundary'
]

valid_contact_verbs = ['splits', 'interrupts', 'contains', 'erodes', 'stops at', 'crosses', 'includes']


class StratigraphicUnitFeature(BaseResqpy):
   """Class for RESQML Stratigraphic Unit Feature objects.

   RESQML documentation:

      A stratigraphic unit that can have a well-known (e.g., "Jurassic") chronostratigraphic top and
      chronostratigraphic bottom. These chronostratigraphic units have no associated interpretations or representations.

      BUSINESS RULE: The name must reference a well-known chronostratigraphic unit (such as "Jurassic"),
      for example, from the International Commission on Stratigraphy (http://www.stratigraphy.org).
   """

   resqml_type = 'StratigraphicUnitFeature'

   def __init__(self,
                parent_model,
                uuid = None,
                top_unit_uuid = None,
                bottom_unit_uuid = None,
                title = None,
                originator = None,
                extra_metadata = None):
      """Initialises a stratigraphic unit feature object."""

      # todo: clarify with Energistics whether the 2 references are to other StratigraphicUnitFeatures or what?
      self.top_unit_uuid = top_unit_uuid
      self.bottom_unit_uuid = bottom_unit_uuid

      super().__init__(model = parent_model,
                       uuid = uuid,
                       title = title,
                       originator = originator,
                       extra_metadata = extra_metadata)

   def is_equivalent(self, other, check_extra_metadata = True):
      """Returns True if this feature is essentially the same as the other; otherwise False."""

      if not isinstance(other, StratigraphicUnitFeature):
         return False
      if self is other or bu.matching_uuids(self.uuid, other.uuid):
         return True
      return (self.title == other.title and ((not check_extra_metadata) or rqo.equivalent_extra_metadata(self, other)))

   def _load_from_xml(self):
      root_node = self.root
      assert root_node is not None
      bottom_ref_uuid = rqet.find_nested_tags_text(root_node, ['ChronostratigraphicBottom', 'UUID'])
      top_ref_uuid = rqet.find_nested_tags_text(root_node, ['ChronostratigraphicTop', 'UUID'])
      # todo: find out if these are meant to be references to other stratigraphic unit features or geologic unit features
      # and if so, instantiate those objects?
      # for now, simply note the uuids
      if bottom_ref_uuid is not None:
         self.bottom_unit_uuid = bu.uuid_from_string(bottom_ref_uuid)
      if top_ref_uuid is not None:
         self.top_unit_uuid = bu.uuid_from_string(top_ref_uuid)

   def create_xml(self, add_as_part = True, originator = None, reuse = True, add_relationships = True):
      """Creates xml for this stratigraphic unit feature."""

      if reuse and self.try_reuse():
         return self.root  # check for reusable (equivalent) object
      # create node with citation block
      suf = super().create_xml(add_as_part = False, originator = originator)

      if self.bottom_unit_uuid is not None:
         self.model.create_ref_node('ChronostratigraphicBottom',
                                    self.model.title(uuid = self.bottom_unit_uuid),
                                    self.bottom_unit_uuid,
                                    content_type = self.model.type_of_uuid(self.bottom_unit_uuid),
                                    root = suf)

      if self.top_unit_uuid is not None:
         self.model.create_ref_node('ChronostratigraphicTop',
                                    self.model.title(uuid = self.top_unit_uuid),
                                    self.top_unit_uuid,
                                    content_type = self.model.type_of_uuid(self.top_unit_uuid),
                                    root = suf)

      if add_as_part:
         self.model.add_part('obj_StratigraphicUnitFeature', self.uuid, suf)
         if add_relationships:
            if self.bottom_unit_uuid is not None:
               self.model.create_reciprocal_relationship(suf, 'destinationObject',
                                                         self.model.root(uuid = self.bottom_unit_uuid), 'sourceObject')
            if self.top_unit_uuid is not None and not bu.matching_uuids(self.bottom_unit_uuid, self.top_unit_uuid):
               self.model.create_reciprocal_relationship(suf, 'destinationObject',
                                                         self.model.root(uuid = self.top_unit_uuid), 'sourceObject')

      return suf


class GeologicUnitInterpretation(BaseResqpy):
   """Class for RESQML Geologic Unit Interpretation objects.

   These objects can be parts in their own right. Various more specialised classes also derive from this.

   RESQML documentation:

      The main class for data describing an opinion of a volume-based geologic feature or unit.
   """

   resqml_type = 'GeologicUnitInterpretation'

   def __init__(
         self,
         parent_model,
         uuid = None,
         title = None,
         domain = 'time',  # or should this be depth?
         geologic_unit_feature = None,
         composition = None,
         material_implacement = None,
         extra_metadata = None):
      """Initialises an geologic unit interpretation object."""

      self.domain = domain
      self.geologic_unit_feature = geologic_unit_feature  # InterpretedFeature RESQML field
      self.has_occurred_during = (None, None)  # optional RESQML item
      if (not title) and geologic_unit_feature is not None:
         title = geologic_unit_feature.feature_name
      self.composition = composition  # optional RESQML item
      self.material_implacement = material_implacement  # optional RESQML item
      super().__init__(model = parent_model, uuid = uuid, title = title, extra_metadata = extra_metadata)
      if self.composition:
         assert self.composition in valid_compositions,  \
            f'invalid composition {self.composition} for geological unit interpretation'
      if self.material_implacement:
         assert self.material_implacement in valid_implacements,  \
            f'invalid material implacement {self.material_implacement} for geological unit interpretation'

   def _load_from_xml(self):
      root_node = self.root
      assert root_node is not None
      self.domain = rqet.find_tag_text(root_node, 'Domain')
      # following allows derived StratigraphicUnitInterpretation to instantiate its own interpreted feature
      if self.resqml_type == 'GeologicUnitInterpretation':
         feature_uuid = bu.uuid_from_string(rqet.find_nested_tags_text(root_node, ['InterpretedFeature', 'UUID']))
         if feature_uuid is not None:
            self.geologic_unit_feature = rqo.GeologicUnitFeature(self.model,
                                                                 uuid = feature_uuid,
                                                                 feature_name = self.model.title(uuid = feature_uuid))
      self.has_occurred_during = rqo.extract_has_occurred_during(root_node)
      self.composition = rqet.find_tag_text(root_node, 'GeologicUnitComposition')
      self.material_implacement = rqet.find_tag_text(root_node, 'GeologicUnitMaterialImplacement')

   def is_equivalent(self, other, check_extra_metadata = True):
      """Returns True if this interpretation is essentially the same as the other; otherwise False."""

      # this method is coded to allow use by the derived StratigraphicUnitInterpretation class
      if other is None or not isinstance(other, type(self)):
         return False
      if self is other or bu.matching_uuids(self.uuid, other.uuid):
         return True
      if self.geologic_unit_feature is not None:
         if not self.geologic_unit_feature.is_equivalent(other.geologic_unit_feature):
            return False
      elif other.geologic_unit_feature is not None:
         return False
      if self.root is not None and other.root is not None:
         if rqet.citation_title_for_node(self.root) != rqet.citation_title_for_node(other.root):
            return False
      elif self.root is not None or other.root is not None:
         return False
      if check_extra_metadata and not rqo.equivalent_extra_metadata(self, other):
         return False
      return (self.composition == other.composition and self.material_implacement == other.material_implacement and
              self.domain == other.domain and
              rqo.equivalent_chrono_pairs(self.has_occurred_during, other.has_occurred_during))

   def create_xml(self, add_as_part = True, add_relationships = True, originator = None, reuse = True):
      """Creates a geologic unit interpretation xml tree."""

      # note: related feature xml must be created first and is referenced here
      # this method is coded to allow use by the derived StratigraphicUnitInterpretation class

      if reuse and self.try_reuse():
         return self.root
      gu = super().create_xml(add_as_part = False, originator = originator)

      assert self.geologic_unit_feature is not None
      guf_root = self.geologic_unit_feature.root
      assert guf_root is not None, 'interpreted feature not established for geologic unit interpretation'

      assert self.domain in self.valid_domains, 'illegal domain value for geologic unit interpretation'
      dom_node = rqet.SubElement(gu, ns['resqml2'] + 'Domain')
      dom_node.set(ns['xsi'] + 'type', ns['resqml2'] + 'Domain')
      dom_node.text = self.domain

      self.model.create_ref_node('InterpretedFeature',
                                 self.geologic_unit_feature.title,
                                 self.geologic_unit_feature.uuid,
                                 content_type = 'obj_GeologicUnitFeature',
                                 root = gu)

      rqo.create_xml_has_occurred_during(self.model, gu, self.has_occurred_during)

      if self.composition is not None:
         assert self.composition in valid_compositions, f'invalid composition {self.composition} for geologic unit interpretation'
         comp_node = rqet.SubElement(gu, ns['resqml2'] + 'GeologicUnitComposition')
         comp_node.set(ns['xsi'] + 'type', ns['resqml2'] + 'GeologicUnitComposition')
         comp_node.text = self.composition

      if self.material_implacement is not None:
         assert self.material_implacement in valid_implacements,  \
            f'invalid material implacement {self.material_implacement} for geologic unit interpretation'
         mi_node = rqet.SubElement(gu, ns['resqml2'] + 'GeologicUnitMaterialImplacement')
         mi_node.set(ns['xsi'] + 'type', ns['resqml2'] + 'GeologicUnitMaterialImplacement')
         mi_node.text = self.material_implacement

      if add_as_part:
         self.model.add_part(self.resqml_type, self.uuid, gu)
         if add_relationships:
            self.model.create_reciprocal_relationship(gu, 'destinationObject', guf_root, 'sourceObject')

      return gu


class StratigraphicUnitInterpretation(GeologicUnitInterpretation):
   """Class for RESQML Stratigraphic Unit Interpretation objects.

   RESQML documentation:

      Interpretation of a stratigraphic unit which includes the knowledge of the top, the bottom,
      the deposition mode.
   """

   resqml_type = 'StratigraphicUnitInterpretation'

   def __init__(
         self,
         parent_model,
         uuid = None,
         title = None,
         domain = 'time',  # or should this be depth?
         geologic_unit_feature = None,
         composition = None,
         material_implacement = None,
         deposition_mode = None,
         min_thickness = None,
         max_thickness = None,
         thickness_uom = None,
         extra_metadata = None):
      """Initialises a stratigraphic unit interpretation object."""

      self.deposition_mode = deposition_mode
      self.min_thickness = min_thickness
      self.max_thickness = max_thickness
      self.thickness_uom = thickness_uom
      super().__init__(model = parent_model,
                       uuid = uuid,
                       title = title,
                       domain = domain,
                       geologic_unit_feature = geologic_unit_feature,
                       composition = composition,
                       material_implacement = material_implacement,
                       extra_metadata = extra_metadata)
      if self.deposition_mode is not None:
         assert self.deposition_mode in valid_deposition_modes
      if self.min_thickness is not None or self.max_thickness is not None:
         assert self.thickness_uom in wam.valid_uoms(quantity = 'length')

   @property
   def stratigraphic_unit_feature(self):
      return self.geologic_unit_feature

   def _load_from_xml(self):
      super()._load_from_xml()
      root_node = self.root
      assert root_node is not None
      feature_uuid = bu.uuid_from_string(rqet.find_nested_tags_text(root_node, ['InterpretedFeature', 'UUID']))
      if feature_uuid is not None:
         self.geologic_unit_feature = StratigraphicUnitFeature(self.model,
                                                               uuid = feature_uuid,
                                                               feature_name = self.model.title(uuid = feature_uuid))
      # load deposition mode and min & max thicknesses (& uom), if present
      self.deposition_mode = rqet.find_tag_text(root_node, 'DepositionMode')
      for min_max in ['Min', 'Max']:
         thick_node = rqet.find_tag(root_node, min_max + 'Thickness')
         if thick_node is not None:
            thick = float(thick_node.text)
            if min_max == 'Min':
               self.min_thickness = thick
            else:
               self.max_thickness = thick
            thick_uom = thick_node.attrib['uom']  # todo: check this is correct uom representation
            if self.thickness_uom is None:
               self.thickness_uom = thick_uom
            else:
               assert thick_uom == self.thickness_uom, 'inconsistent length units of measure for stratigraphic thicknesses'

   def is_equivalent(self, other, check_extra_metadata = True):
      """Returns True if this interpretation is essentially the same as the other; otherwise False."""
      if not super().is_equivalent(other):
         return False
      if self.deposition_mode is not None and other.deposition_mode is not None:
         return self.deposition_mode == other.deposition_mode
      return True

   def create_xml(self, add_as_part = True, add_relationships = True, originator = None, reuse = True):
      """Creates a stratigraphic unit interpretation xml tree."""

      if reuse and self.try_reuse():
         return self.root
      sui = super().create_xml(add_as_part = add_as_part,
                               add_relationships = add_relationships,
                               originator = originator,
                               reuse = False)
      assert sui is not None

      if self.deposition_mode is not None:
         assert self.deposition_mode in valid_deposition_modes,  \
            f'invalid deposition mode {self.deposition_mode} for stratigraphic unit interpretation'
         dm_node = rqet.SubElement(sui, ns['resqml2'] + 'DepositionMode')
         dm_node.set(ns['xsi'] + 'type', ns['resqml2'] + 'DepositionMode')
         dm_node.text = self.deposition_mode

      if self.min_thickness is not None or self.max_thickness is not None:
         assert self.thickness_uom in wam.valid_uoms(quantity = 'length')

      if self.min_thickness is not None:
         min_thick_node = rqet.SubElement(sui, ns['resqml2'] + 'MinThickness')
         min_thick_node.set(ns['xsi'] + 'type', ns['eml'] + 'LengthMeasure')
         min_thick_node.set('uom', self.thickness_uom)  # todo: check this
         min_thick_node.text = str(self.min_thickness)

      if self.max_thickness is not None:
         max_thick_node = rqet.SubElement(sui, ns['resqml2'] + 'MaxThickness')
         max_thick_node.set(ns['xsi'] + 'type', ns['eml'] + 'LengthMeasure')
         min_thick_node.set('uom', self.thickness_uom)
         max_thick_node.text = str(self.max_thickness)

      return sui


class StratigraphicColumn(BaseResqpy):
   """Class for RESQML stratigraphic column objects.

   RESQML documentation:

      A global interpretation of the stratigraphy, which can be made up of
      several ranks of stratigraphic unit interpretations.

      All stratigraphic column rank interpretations that make up a stratigraphic column
      must be ordered by age.
   """

   resqml_type = 'StratigraphicColumn'

   # todo: integrate with EarthModelInterpretation class which can optionally refer to a stratigraphic column

   def __init__(self, parent_model, uuid = None, rank_uuid_list = None, title = None, extra_metadata = None):
      """Initialises a Stratigraphic Column object.

      arguments:
         rank_uuid_list (list of uuid, optional): if not initialising for an existing stratigraphic column,
            the ranks can be established from this list of uuids for existing stratigraphic column ranks;
            ranks should be ordered from geologically oldest to youngest
      """

      self.ranks = []  # list of Stratigraphic Column Rank Interpretation objects

      super().__init__(model = parent_model, uuid = uuid, title = title, extra_metadata = extra_metadata)

      if self.root is None and rank_uuid_list:
         for rank_uuid in rank_uuid_list:
            rank = StratigraphicColumnRank(self.model, uuid = rank_uuid)
            self.add_rank(rank)

   def _load_from_xml(self):
      rank_node_list = rqet.list_of_tag(self.root, 'Ranks')
      assert rank_node_list is not None, 'no stratigraphic column ranks in xml for stratigraphic column'
      for rank_node in rank_node_list:
         rank = StratigraphicColumnRank(self.model, uuid = rqet.uuid_for_part_root(rank_node))
         self.add_rank(rank)

   def iter_ranks(self):
      """Yields the stratigraphic column ranks which constitute this stratigraphic colunn."""

      for rank in self.ranks:
         yield rank

   def add_rank(self, rank):
      """Adds another stratigraphic column rank to this stratigraphic column.

      arguments:
         rank (StratigraphicColumnRank): an established rank to be added to this stratigraphic column

      note:
         ranks should be ordered from geologically oldest to youngest
      """
      assert rank is not None
      self.ranks.append(StratigraphicColumnRank(self.model, uuid = rank.uuid))

   def is_equivalent(self, other, check_extra_metadata = True):
      """Returns True if this interpretation is essentially the same as the other; otherwise False."""

      if not isinstance(other, StratigraphicColumn):
         return False
      if self is other or bu.matching_uuid(self.uuid, other.uuid):
         return True
      if len(self.ranks) != len(other.ranks):
         return False
      for rank_a, rank_b in zip(self.ranks, other.ranks):
         if rank_a != rank_b:
            return False
      if check_extra_metadata and not rqo.equivalent_extra_metadata(self, other):
         return False
      return True

   def create_xml(self, add_as_part = True, add_relationships = True, originator = None, reuse = True):
      """Creates xml tree for a stratigraphic column object."""

      assert self.ranks, 'attempt to create xml for stratigraphic column without any contributing ranks'

      if reuse and self.try_reuse():
         return self.root

      sci = super().create_xml(add_as_part = False, originator = originator)

      assert sci is not None

      for rank in self.ranks:
         self.model.create_ref_node('InterpretedFeature',
                                    rank.title,
                                    rank.uuid,
                                    content_type = 'obj_StratigraphicColumnRankInterpretation',
                                    root = sci)

      if add_as_part:
         self.model.add_part('obj_StratigraphicColumn', self.uuid, sci)
         if add_relationships:
            for rank in self.ranks:
               self.model.create_reciprocal_relationship(sci, 'destinationObject', rank.root, 'sourceObject')

      return sci


class StratigraphicColumnRank(BaseResqpy):
   """Class for RESQML StratigraphicColumnRankInterpretation objects."""

   resqml_type = 'StratigraphicColumnRankInterpretation'

   # list of contact interpretations (optional)
   # list of one or more stratigraphic unit interpretations, each with a local index from oldest (0) to youngest

   # interpreted feature: an earth model feature
   # ordering criterion: must be 'age'
   # domain
   # index: 0 if only one rank; otherwise indicates nested rank of the column?
   # has occured during: optional geo time period (organize.py has some relevant code)

   # TODO
   pass


class ContactInterpretation:
   """General class for contact between 2 geological entities; not a high level class but used by others."""

   def __init__(self, index: int, contact_relationship: str, subject, verb: str, direct_object, part_of = None):
      # index (non-negative integer, should increase with decreasing age for horizon contacts)
      # contact relationship (one of valid_contact_relationships)
      # subject (reference to e.g. stratigraphic unit interpretation)
      # verb (one of valid_contact_verbs)
      # direct object (reference to e.g. stratigraphic unit interpretation)
      # part of (reference to e.g. horizon interpretation, optional)

      # TODO
      pass
