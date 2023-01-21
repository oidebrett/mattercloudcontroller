from abc import ABC, abstractmethod

import chip.clusters as Clusters


class DataModelLookup(ABC):
    @abstractmethod
    def get_cluster(self, cluster: str):
        pass

    @abstractmethod
    def get_command(self, cluster: str, command: str):
        pass

    @abstractmethod
    def get_attribute(self, cluster: str, attribute: str):
        pass

    @abstractmethod
    def get_event(self, cluster: str, event: str):
        pass


class PreDefinedDataModelLookup(DataModelLookup):
    def get_cluster(self, cluster: str):
        try:
            return getattr(Clusters, cluster, None)
        except AttributeError:
            return None

    def get_command(self, cluster: str, command: str):
        try:
            commands = getattr(Clusters, cluster, None).Commands
            return getattr(commands, command, None)
        except AttributeError:
            return None

    def get_attribute(self, cluster: str, attribute: str):
        try:
            attributes = getattr(Clusters, cluster, None).Attributes
            return getattr(attributes, attribute, None)
        except AttributeError:
            return None

    def get_event(self, cluster: str, event: str):
        try:
            events = getattr(Clusters, cluster, None).Events
            return getattr(events, event, None)
        except AttributeError:
            return None