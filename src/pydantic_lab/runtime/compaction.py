"""Log native summarization without implementing a second context reducer."""

from dataclasses import dataclass

from pydantic_ai_harness.compaction import SummarizingCompaction, estimate_token_count

from pydantic_lab.storage.control import ControlStore


@dataclass(kw_only=True)
class LoggedCompaction(SummarizingCompaction):
    store: ControlStore
    session_id: str
    logical_run_id: str

    async def before_model_request(self, ctx, request_context):
        before = estimate_token_count(request_context.messages)
        count = len(request_context.messages)
        result = await super().before_model_request(ctx, request_context)
        after = estimate_token_count(result.messages)
        if before != after or count != len(result.messages):
            self.store.emit(
                self.session_id,
                "compaction.completed",
                run_id=self.logical_run_id,
                reason="context_threshold",
                before=before,
                after=after,
                estimated=True,
            )
        return result
