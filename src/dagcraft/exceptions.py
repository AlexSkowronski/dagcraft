class DagcraftError(Exception):
    """
    Base Dagcraft exception.
    """


class ConfigError(DagcraftError):
    """
    Raised when pipeline configuration is invalid.
    """


class GraphError(DagcraftError):
    """
    Raised when the DAG cannot be compiled.
    """


class RegistryError(DagcraftError):
    """
    Raised when a registered component cannot be found.
    """


class ExecutionError(DagcraftError):
    """
    Raised when pipeline execution fails.
    """
