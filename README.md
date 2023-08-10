# Optimizing Fantasy Football Auction Drafts utilizing Linear Programming

Fantasy football auction drafts can be formulated as a Linear Programming optimization problem. The simplest form assumes that the projected points and bid value stays constant throughout the draft. While that assumption is likely to hold for projected points, it is not for the bid value. Bid value is a dynamic variable that is dependent on team budgets, team needs, and personal biases. However, for pre-draft analysis, this is a valid assumption as the output is useful.

## LP Problem Formulation

Let binary decision variables  be $X_{i}$ where $X_{i} \in {[0, 1]}$ 
indicating whether player $X_{i}$ is drafted.

$$\begin{aligned}
 \text{Maximize} && \sum{p_{i}x_{i}}\\
 \text{subject to:}\\
 \text{QBs:} && x_{i\in QB} = 1 && (1)\\
 \text{RBs:} && x_{i\in RB} >= 2 && (2) \\
 \text{WRs:}&& x_{i\in WR} >= 2 && (3)  \\
 \text{TEs:}&& x_{i\in TE} >= 2 && (4) \\
 \text{K:}&& x_{i\in K} = 1 && (5) \\
 \text{Flex:}&& x_{i\in RB} + x_{i\in WR} + x_{i\in TE} <= 6 && (6) \\
 \text{Def:}&& x_{i\in DST} = 1 && (7) \\
 \text{Budget:}&& x_{i}c_{i} <= 200 && (8) \\
\end{aligned}$$

Where:
- Constraints (1)-(7) are positional constraints (i.e., cannot start more than 1 QB)
- $p_{i}$ is the projected value of player $x_{i}$ over the course of a season
- $c_{i}$ is the projected value bid of player $x_{i}$

## Results
With a $200 budget, this is the optimal team (does not take bench into account)

| player              | pos | proj pts | bid  |
|---------------------|-----|----------|------|
| Christian McCaffrey | rb  | 269.5    | 49.0 |
| Austin Ekeler       | rb  | 261.0    | 46.0 |
| Patrick Mahomes II  | qb  | 383.9    | 33.0 |
| Amon-Ra St. Brown   | wr  | 208.3    | 28.0 |
| T.J. Hockenson      | te  | 157.8    | 20.0 |
| Chris Godwin        | wr  | 170.5    | 12.0 |
| Diontae Johnson     | wr  | 154.3    | 9.0  |
| Dallas Cowboys      | dst | 119.3    | 2.0  |
| Zane Gonzalez       | k   | 130.5    | 1.0  |

While it's unlikely that you'll be able to produce this team, the bid value will also give an approximate value on each position and the bid value distribution to acheive an optimal team.

## Data
All data was downloaded from Fantasypros.com. The data includes the projected bid and points.
