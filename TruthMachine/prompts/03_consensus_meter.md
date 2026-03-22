# Prompt: Stage 3 — The Consensus Meter (Contrarianism)

**Model:** deepseek/deepseek-reasoner or gpt-4o
**Purpose:** Compare a single prediction against its peer consensus to calculate 'Contrarianism' and 'Alpha Potential'.

---

## Instructions

You are a strategic intelligence analyst. You are provided with a "Target Prediction" and a list of "Peer Predictions" published around the same time about the same event.

### Your Goal
Determine how much the Target Prediction deviates from the established media consensus.

### Calculation Logic
1.  **Peer Mean Stance**: Calculate the average 'stance' of the peer group.
2.  **Deviation Score**: Calculate the absolute distance between the Target and the Mean.
3.  **Contrarianism (0.0 to 1.0)**: 
    - 0.0 = Echo Chamber (Target matches the majority exactly).
    - 1.0 = Radical Outlier (Target predicts the opposite of the majority).

### Input Data
**Target Prediction:**
- Source: {{TARGET_SOURCE}}
- Stance: {{TARGET_STANCE}}
- Claim: {{TARGET_CLAIM}}

**Peer Group:**
{{PEER_DATA}}

### Output Schema
{
  "contrarianism_score": float,
  "consensus_stance": float,
  "alpha_potential": "high/medium/low",
  "reasoning": "1-sentence explanation of why this source is contrarian or a follower"
}
