## req_026_break_up_the_1153_line_session_service_factory_before_splitting_its_file - Break up the 1153-line session service factory before splitting its file
> From version: 0.14.0
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Maintainability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-07

# Needs
- `src/session_service.py` is 1652 lines, but its size is a symptom. `create_session_service` alone spans 1153 of them and defines 46 closures inside a single function body.
- Because the behavior lives in closures over the factory's locals, none of it can be tested, read, or moved independently. Splitting the file while that holds would produce several files that still cannot be reasoned about separately.
- This is the opposite problem from `req_025`'s command file. There the domains were already independent and only shared a filename; here they share a scope, so the decomposition has to come before, not after, any file split.
- The closures cluster by concern — roughly 19 on session CRUD, 8 on backup and bundles, 7 on status, 5 on launch and history, 4 on auth — so the seams exist; they are just not expressible while everything closes over the same locals.

# Context
- `create_session_service` starts at line 499 and runs to the end of the module. The 25 module-level functions before it are already ordinary functions and are not the problem.
- The 46 inner closures are returned as a dict of callables, which is the service interface every caller uses. That interface is what must not change.
- The closures capture factory locals such as the resolved base directory, the session store, and cached state. Turning one into a module-level function means passing what it currently captures, which is the actual work of this request.
- Ordering constraint: `req_025` splits the command file and explicitly excludes this one. This request should not start before that pilot has reported, so a regression in either is attributable to one of them rather than to both at once.
- `test/test_session_service_py.py` is 2055 lines and exercises the service almost entirely through the returned dict, so it is a usable regression net for a decomposition that preserves that dict.

# Acceptance criteria
- AC1: The service interface is unchanged: `create_session_service` returns a dict with the same keys and the same callable behavior, so no caller is touched.
- AC2: Behavior that does not need the factory's locals becomes a module-level function, testable directly rather than only through the returned dict.
- AC3: Behavior that does need factory state receives it explicitly rather than capturing it, so what a piece depends on is visible in its signature.
- AC4: `create_session_service` is materially smaller, and what remains in it is assembly rather than logic.
- AC5: The decomposition is a sequence of behavior-preserving moves, each with the full suite passing, not one large rewrite.
- AC6: No file split happens in this request. Whether to split the file, and along which seam, is decided once the closures have become functions and the seams are real.
- AC7: Tests are added for the newly extractable behavior only where extracting it made something testable that was not before; existing tests are not rewritten to match the new shape.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_016_a_session_service_that_can_be_read_in_pieces`
- Architecture decision(s): (none yet)

# References
- src/session_service.py
- src/session_store.py
- test/test_session_service_py.py
- test/test_session_service_helpers_py.py

# AI Context
- Summary: Break up the 1153-line session service factory before splitting its file
- Keywords: request-chain-scaffold, break up the 1153-line session service factory before splitting its file, development-ready
- Use when: You need to implement or review the scaffolded workflow for Break up the 1153-line session service factory before splitting its file.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_057_lift_the_closures_that_capture_nothing_into_module_level_functions`
- `item_058_give_the_state_dependent_closures_explicit_dependencies`
- `item_059_decide_the_file_split_from_the_seams_the_decomposition_exposed`
