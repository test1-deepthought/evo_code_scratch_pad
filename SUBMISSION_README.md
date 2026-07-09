# ARC-AGI-3 Competition Submission

## SystematicExplorerAgent

A meta-reasoning agent for the ARC Prize 2026 (ARC-AGI-3) competition.

## How to Use

1. **Clone the competition repo:**
   ```bash
   git clone https://github.com/arcprize/ARC-AGI-3-Agents.git
   cd ARC-AGI-3-Agents
   ```

2. **Copy the agent files:**
   Copy `agents/templates/systematic_explorer.py` to `ARC-AGI-3-Agents/agents/templates/`
   Copy `agents/__init__.py` to `ARC-AGI-3-Agents/agents/` (merged with existing)

3. **Set up environment:**
   ```bash
   cp .env.example .env
   # Add your ARC_API_KEY from https://three.arcprize.org/
   # Add your OPENAI_API_KEY
   ```

4. **Run the agent:**
   ```bash
   # Single game
   uv run main.py --agent=systematicexploreragent --game=locksmith
   
   # All games (using swarm)
   uv run python -c "
   from agents import Swarm
   swarm = Swarm(agent='systematicexploreragent',
                 ROOT_URL='https://three.arcprize.org',
                 games=['locksmith', 'ls20'])
   swarm.main()
   "
   ```

5. **Submit:**
   Fill out the ARC Prize submission form:
   https://forms.gle/wMLZrEFGDh33DhzV9

## Architecture

The SystematicExplorerAgent uses a phase-based approach:

1. **INITIAL_RESET** - Reset the game to start
2. **DISCOVER_ACTIONS** - Test each action type to learn what it does
3. **MAP_GRID** - Explore the grid structure systematically
4. **FIND_GOAL** - Use LLM reasoning to understand the objective
5. **SOLVE** - Execute the solution plan
6. **RECOVERY** - Recover from failures

## Requirements
- ARC_API_KEY (from https://three.arcprize.org/)
- OPENAI_API_KEY (for LLM reasoning mode)
- Python 3.12+
- uv package manager
