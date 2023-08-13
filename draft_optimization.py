# Set up
import pandas as pd
import gurobipy as grb
import numpy as np

def clean_currency(x):
    """ If the value is a string, then remove currency symbol and delimiters
    otherwise, the value is numeric and can be converted
    """
    if isinstance(x, str):
        return(x.replace('$', '').replace(',', ''))
    return(x)

def prep_bid_data(projected_bid):
    projected_bid['pos'] = projected_bid['Overall'].str.extract(r'((?<= - ).*\))')
    projected_bid['pos'] = projected_bid['pos'].str[:-1].str.lower()
    projected_bid['name'] = projected_bid['Overall'].str.replace(r' \(.*', '', regex=True)
    projected_bid['Projected'] = projected_bid['Projected'].apply(clean_currency).astype('float')
    projected_bid['Value'] = np.where(projected_bid['Actual'].notnull(), projected_bid['Actual'], projected_bid['Projected'])
    return projected_bid

def merge_with_bid(positional_data, bid_data, pos):
    value_data = positional_data.merge(bid_data, how = 'left', left_on = 'Player', right_on = 'name')
    value_data['Value'] = value_data['Value'].apply(clean_currency).astype('float')
    value_data = value_data[value_data['Value'] >= 0]
    value_data = pd.DataFrame({'player': value_data['Player'], 'pts': value_data['FPTS'], 'bid': value_data['Value'], 'pos': pos})
    return value_data


def get_player_data():
    # Read in projected bid data and remove team names from player name
    projected_bid = pd.read_csv('./data/projected_bid.csv')
    projected_bid = prep_bid_data(projected_bid)
    
    # Read in positional data
    data = {}
    data['qb'] = pd.read_csv('./data/FantasyPros_Fantasy_Football_Projections_QB.csv')
    data['rb'] = pd.read_csv('./data/FantasyPros_Fantasy_Football_Projections_RB.csv')
    data['wr'] = pd.read_csv('./data/FantasyPros_Fantasy_Football_Projections_WR.csv')
    data['te'] = pd.read_csv('./data/FantasyPros_Fantasy_Football_Projections_TE.csv')
    data['k'] = pd.read_csv('./data/FantasyPros_Fantasy_Football_Projections_K.csv')
    data['dst'] = pd.read_csv('./data/FantasyPros_Fantasy_Football_Projections_DST.csv')
    
    
    positions = ['qb', 'rb', 'wr', 'te', 'k', 'dst']
    pos_data = {}
    for p in positions:
        pos_data[p] = merge_with_bid(data[p], projected_bid, p)
    
    for p in positions:
        if p == positions[0]:
            player_data = pos_data[p]
        else:
            player_data = pd.concat([player_data, pos_data[p]])
    
    player_data['pts'] = player_data['pts']/17
    
    pos_cap_dict = {'qb': 1, 'rb':2, 'wr': 2, 'te': 1, 'k': 1, 'dst': 1, 'flex': 1}
    
    
    # position player list
    positions = ['qb', 'rb', 'wr', 'te', 'k', 'dst']
    flex_positions = ['rb', 'wr', 'te']
    
    pos_dict = {}
    for p in positions:
        pos_dict[p] = player_data[player_data['pos'] == p]['player']

    return player_data, positions, flex_positions, pos_dict, pos_cap_dict, projected_bid

def create_dv(player_data, positions, mod):
    x = {}
    for p in positions:
        tmp_df = player_data[player_data['pos']==p]
        for index, row in tmp_df.iterrows():
            i = row['player']
            x[i, p]=mod.addVar(lb=0,name='x[{0},{1}]'.format(i, p), vtype=grb.GRB.BINARY)
    return x

def pos_capacity_constraint(positions, flex_positions, x, player_data, pos_cap_dict, mod, pos_dict):
    # position capacity constraint
    for p in positions:
        if p in flex_positions:
            mod.addConstr(sum(x[i, p] for i in player_data[player_data['pos']==p]['player']) >= pos_cap_dict[p],name=p + ' positional constraint')    
        else:
            mod.addConstr(sum(x[i, p] for i in player_data[player_data['pos']==p]['player']) == pos_cap_dict[p],name=p + ' positional constraint')
    
    # flex position constraint
    flex_constraint = {}
    flex_max = sum(pos_cap_dict[p] for p in flex_positions) + pos_cap_dict['flex']
    for f in flex_positions:
        flex_constraint[f] = sum(x[i, f] for i in pos_dict[f])
    
    mod.addConstr(sum(flex_constraint[f] for f in flex_positions) <= flex_max, name = 'flex constraint')

def budget_constraint(positions, budget, pos_dict, player_data, x, mod):
    budgets = {}
    for p in positions:
        budgets[p] = sum(x[i, p] * player_data[(player_data['player'] == i) & (player_data['pos'] == p)]['bid'] for i in pos_dict[p])
    mod.addConstr(sum(budgets[p] for p in positions) <= budget, name = 'budget constraint')

def drafted_constraint(x, drafted_players, mod):
    for index, row in drafted_players.iterrows():
        i = row['name']
        p = row['pos']
        mod.addConstr(x[i, p] == 1, name = i + ' draft constraint')

def taken_constraint(x, taken_players, mod):
    for index, row in taken_players.iterrows():
        i = row['name']
        p = row['pos']
        mod.addConstr(x[i, p] == 0, name = i + ' taken constraint')


def run_lp(budget, positions, player_data, pos_dict, pos_cap_dict, player_eval, projected_bid, flex_positions):

    # initalize model
    mod=grb.Model()
    mod.Params.LogToConsole = 0
    
    # Create decision variables
    x = create_dv(player_data, positions, mod)
    
    # position capacity constraint
    pos_capacity_constraint(positions, flex_positions, x, player_data, pos_cap_dict, mod, pos_dict)
    
    # budget constraint
    budget_constraint(positions, budget, pos_dict, player_data, x, mod)

    # players drafted constraint
    drafted_players = projected_bid[projected_bid['Status'] == 'drafted']
    drafted_constraint(x, drafted_players, mod)

    # taken player constraint
    taken_players = projected_bid[projected_bid['Status'] == 'x']
    taken_constraint(x, taken_players, mod)
    
    # players evaluated constraint
    if player_eval[0]:
        eval_name = projected_bid[projected_bid['Status'] == 'evaluate']['name'].values[0]
        eval_pos = projected_bid[projected_bid['Status'] == 'evaluate']['pos'].values[0]
        if player_eval[1]:
            mod.addConstr(x[eval_name, eval_pos] == 1, name = eval_name + " eval constraint")
        else:
            mod.addConstr(x[eval_name, eval_pos] == 0, name = eval_name + " eval constraint")
    
    # optimize function
    optimize = {}
    for p in positions:
        optimize[p] = sum(x[i, p] * player_data[(player_data['player'] == i) & (player_data['pos'] == p)]['pts'] for i in pos_dict[p])
    
    mod.setObjective(sum(optimize[p] for p in positions),sense=grb.GRB.MAXIMIZE)
    mod.optimize()
    return mod
    
def get_optimal_team(player_data, mod):
    optimal_draft = pd.DataFrame({'players': player_data['player'], 'draft_status': mod.X, 'pos': player_data['pos'], 'pts': player_data['pts'], 'bid': player_data['bid']})
    optimal_draft.pts = optimal_draft.pts.round(2)
    optimal_draft.bid = optimal_draft.bid.round(0)
    optimal_draft = optimal_draft[optimal_draft['draft_status'] == 1].sort_values('bid', ascending = False)[['players', 'pos', 'pts', 'bid']]
    return optimal_draft.reset_index(drop=True)

def evaluate_player(optimal_value):
    player_data, positions, flex_positions, pos_dict, pos_cap_dict, projected_bid = get_player_data()

    threshold = 0
    
    eval_name = projected_bid[projected_bid['Status'] == 'evaluate']['name'].values[0]
    eval_pos = projected_bid[projected_bid['Status'] == 'evaluate']['pos'].values[0]

    initial_budget = 200
    budget = initial_budget - sum(projected_bid[projected_bid['Status'] == 'drafted']['Value'])
    player_eval_df = pd.DataFrame({'Bid': [], 'Pts': []})
    
    premium = list(range(0, 105,5))
    player_eval = [True, False]
    mod = run_lp(budget, positions, player_data, pos_dict, pos_cap_dict, player_eval, projected_bid, flex_positions)
    
    player_eval_df=pd.concat([player_eval_df, pd.DataFrame({'Bid': [-1], 'Pts': [round(mod.ObjVal, 2)]})])
    
    # don't draft
    player_eval = [True, True]
    
    # draft at different values
    for new_bid in premium:
        player_data.loc[player_data.player == eval_name, 'bid'] = new_bid
        mod = run_lp(budget, positions, player_data, pos_dict, pos_cap_dict, player_eval, projected_bid, flex_positions)
        try:
            player_eval_df=pd.concat([player_eval_df, pd.DataFrame({'Bid': [new_bid], 'Pts': [round(mod.ObjVal, 2)]})])
            if round(mod.ObjVal, 2) > optimal_value:
                threshold = new_bid
        except:
            break

    return player_eval_df.reset_index(drop=True), threshold

def main():
    ### MAIN
    player_data, positions, flex_positions, pos_dict, pos_cap_dict, projected_bid = get_player_data()

    drafted_players = projected_bid[projected_bid['Status'] == 'drafted']['name']

    initial_budget = 200
    
    budget = initial_budget - sum(projected_bid[projected_bid['Status'] == 'drafted']['Value'])

    player_eval = [False, False]
    mod = run_lp(budget, positions, player_data, pos_dict, pos_cap_dict, player_eval, projected_bid, flex_positions)
    print("############### OPTIMAL DRAFT RESULTS ###############")

    optimal_value = round(mod.ObjVal, 2)

    print("\nOPTIMAL POINTS: " + str(optimal_value))
    optimal_lineup = get_optimal_team(player_data, mod)
    optimal_lineup_draft_status = optimal_lineup.merge(drafted_players, how = 'left', left_on = 'players', right_on = 'name')
    optimal_lineup_draft_status['name'] = np.where(optimal_lineup_draft_status['name'].notnull(), optimal_lineup_draft_status['players'] + ' (d)', optimal_lineup_draft_status['players'])
    optimal_lineup_draft_status = optimal_lineup_draft_status[['name', 'pos', 'pts', 'bid']]

    print("OPTIMAL DRAFT:")
    print(optimal_lineup_draft_status)
    if len(projected_bid[projected_bid['Status'] == 'evaluate']['name']) > 0:        
        player_name_eval = projected_bid[projected_bid['Status'] == 'evaluate']['name'].values[0]
        player_evaluation, threshold = evaluate_player(optimal_value)
        print("\n############# " + player_name_eval.upper() + " ###############")
        print("\nDRAFT VALUE: " + str(threshold))
        print(player_evaluation)

if __name__ == "__main__":
    main()
