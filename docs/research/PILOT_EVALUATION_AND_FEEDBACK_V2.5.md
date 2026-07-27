# Pilot Evaluation and Feedback v2.5

The platform now stores structured user feedback, evaluation campaigns and responses. The safe pilot instrument is located at `data/evaluation/pilot_evaluation_instrument_v2.5.json`.

## Evaluation dimensions

- task success;
- pedagogical quality;
- academic and qualification-level alignment;
- source integrity;
- usability and accessibility;
- trust and assessment safety;
- efficiency and time saved.

## Evidence rules

Evaluation records identify tenant, participant, role, task reference, output version and timestamps. Research consent is separate from ordinary product feedback. An institution may use operational feedback without automatically treating it as research data.

## Benchmark separation

Evaluation cases must not be placed in retrieval indexes or model-adaptation datasets. Provider comparison must use the same prompt, module context, source pack and scoring rubric. Expert ratings should be blinded to provider where practical.

## Acceptance gate

A commercial pilot cannot pass solely on average satisfaction. Critical failures in tenant isolation, assessment confidentiality, fabricated sources, unauthorised release or reviewer access are release blockers irrespective of aggregate scores.
