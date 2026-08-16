class LegalReferenceRoleBatchProcessor:
    def __init__(self,runtime):
        self.runtime=runtime
        self._seen=set()
    def process(self,case_scope_id,source_entity_type,source_entity_id,scenario):
        key=(case_scope_id,source_entity_id)
        if key in self._seen:
            return None
        self._seen.add(key)
        return self.runtime.extract(case_scope_id,source_entity_type,source_entity_id,scenario)
