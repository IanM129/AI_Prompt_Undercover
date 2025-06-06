import os
import sys
import random
import pandas as pd
import pyperclip
import re

from openai import OpenAI
# Load API key in environment
from dotenv import load_dotenv
load_dotenv()

#### Settings
global player_count, cur_player_count
player_count = 5;
cur_player_count = player_count;
mrwhite_included = True;
manual_enter_output = False;
pause_between = True;
full_debug = False;
####


#### Utilities
def turn_word(n):
    match (n):
        case 1: return "first";
        case 2: return "second";
        case 3: return "third";
        case 4: return "fourth";
        case 5: return "fifth";
        case 6: return "sixth";
    return str(n);
def role_text(role):
    if (role == 3): return "Mr. White";
    if (role == 2): return "Undercover";
    if (role == 1): return "Civilian";
    if (role == 0): return "Eliminated";
    return "ERROR: INVALID ROLE VALUE";
def roles_text(undercover : bool, mrwhite : bool):
    role_cnt = 1 + (1 if undercover else 0) + (1 if mrwhite else 0);
    text = f"{role_cnt} roles: the Civilians";
    if (undercover and mrwhite):
        text += ", the Undercover and Mr. White.";
    else:
        text += " and " + ("the Undercover" if undercover else "Mr. White") + ".";
    text += "There are " + str(cur_player_count - (2 if mrwhite else 1)) + " Civilians and they all receive the same word.";
    if (undercover): text += " One of the players is the Undercover and they receive a different, but similar word.";
    if (mrwhite):
        if (undercover): text += " Another player is ";
        else: text += " One of the players is ";
        text += "Mr. White and they do not receive a word, but must blend in.";
    return text;
def game_state_string():
    res = "The states/roles are:\n";
    for i in range(1, player_count + 1):
        res += f"    Player {i} is " + ("Mr. White" if roles[i] == 3 else ("Undercover" if roles[i] == 2 else ("a Civilian" if roles[i] == 1 else "eliminated"))) + "\n";
    return res;
def check_victory(roles):
    cnt_civ = 0; cnt_und = 0; white_ex = False;
    for i in range(1, len(roles) + 1):
        if (roles[i] == 1): cnt_civ += 1;
        elif (roles[i] == 2): cnt_und += 1;
        elif (roles[i] == 3): white_ex = True;
    # check
    if white_ex == True:
        if cnt_und + cnt_civ == 1: return 3;
    else:
        if cnt_und == 0: return 1;
        if cnt_civ == cnt_und: return 2;
    return -1;
def kick_player(player_num):
    # if no one
    if (player_num == -1):
        print("-- No one was kicked out, votes are tied.");
        return;
    global cur_player_count;
    # if Mr. White
    if (roles[player_num] == 3):
        print("-- Mr. White is voted out, they have a chance to guess the Civilian word:");
        instruction = get_instruction(player_num, 3, turn, context if context_ex else {});
        prompt = get_input_mrwhite_voted();
        if (manual_enter_output):
                print(f"-- Prompt for player {player_num} (Mr. White):");
                print(instruction);
                print(prompt);
                pyperclip.copy(instruction + "\n" + prompt);
                print("-- Enter answer (single word):");
                output = input("");
        else:
            response = prompt_client(player_num, instruction, prompt);
            output, valid = process_response(response, False);
            while (not valid):
                print("-- Can't detect requested content in response, enter blank to retry or enter the answer manually:");
                manual = input("");
                if (manual == ""):
                    response = prompt_client(player_num, instruction, prompt);
                else:
                    response = manual;
                output, valid = process_response(response, False);
            print(f"-> Detected answer: '{output}'");
        if (output.lower().strip() == civilian_word.lower().strip()):
            print("--------> Mr. White guessed the word, game is over!");
            print("---- MR. WHITE WINS ----");
            input("Press enter to exit...");
            sys.exit(0);
    context[-1][turn] = str(voted_out);
    role = roles[voted_out];
    roles[voted_out] = 0;
    cur_player_count -= 1;
    print("Voted out: Player " + str(voted_out) + ", they were " + ("Mr. White" if role == 3 else ("Undercover" if role == 2 else "a Civilian.")));
####


# Load majority and undercover word pairs
word_pairs = pd.read_csv("wordPairs.csv");
#print(word_pairs)

# Choose pair:
chosen_pair = random.randint(0, len(word_pairs) - 1);
civilian_word = word_pairs['majority'][chosen_pair];
undercover_word = word_pairs['undercover'][chosen_pair];
# Choose roles:
global undercover_active, mrwhite_active
roles = {};
undercover_ind = 2; #random.randint(0, player_count - 1)
undercover_active = True;
mrwhite_active = False;
if (mrwhite_included):
    white_ind = 4; #random.randint(1, player_count - 1);
    while (white_ind == 0 or white_ind == 1 or white_ind == undercover_ind):
        white_ind = random.randint(1, player_count - 1);
    mrwhite_active = True;
for i in range(player_count):
    roles[i + 1] = 3 if white_ind == i else (2 if undercover_ind == i else 1);


#### Prompt template
def context_string(context : dict[dict], cur_player : int, print_voted : bool = False):
    res = "";
    for turn_num in context:
        if (turn_num > 0 and len(context[turn_num]) > 0):
            res += "\nIn turn " + str(turn_num) + " the next things happened:\n";
            turn = context[turn_num];
            for player_num in turn:
                if (roles[player_num] > 0):
                    if (cur_player != player_num):
                        res += ("You" if (cur_player == player_num) else ("Player " + str(player_num))) + ' said: "' + turn[player_num] + '".\n';
            # Don't add voted out players to prompt, confuses them
            if (print_voted):
                if -1 in context and turn_num in context[-1]:
                    kicked = int(context[-1][turn_num]);
                    res += "Player " + str(kicked) + " was voted out, they were " + ("Mr. White" if roles[kicked] == 3 else ("Undercover" if roles[kicked] == 2 else "a Civilian")) + ".\n";
    return res;
def get_input(vote):
    prom = "";
    if (vote):
        prom += "Who do you vote for that you think is the Undercover" + (" or Mr. White" if mrwhite_active else "") + \
                "? Give a response with only a single number and no explanation or reasoning. You cannot vote for yourself.";
    else:
        prom += "What word do you say for this turn? Give a response with only a single word and no explanation or reasoning.";
    return prom;
def get_input_mrwhite_voted():
    prom = "You are Mr. White and you have been voted out. You now have the chance to guess which word the Civilians were given based on the given context, what is your guess? Reply in a single word without any explanations or reasoning.";
    return prom;
# 3+ players -> one undercover, one mr white
def get_instruction(player_num : int, role : int, turn_count = 1, context = {}):
    #inst = "Return all responses as a single word.\n";
    inst = f"You are playing the Undercover board game with {cur_player_count - 1} other players left in the game. There are " + roles_text(undercover_active, mrwhite_active) + \
            " The game is played in turns: first every player says a word, which cannot be the same as an already said word. Then everyone votes on who they think the Undercover" + (" or Mr. White" if mrwhite_active else "") + " is based on the words they said throughout the game, and then the most voted player gets kicked out and loses the game. " + \
            "The goal of the Civilians is to vote out the Undercover, while the goal of the Undercover" + (" and Mr. White" if mrwhite_active else "") + " is to stay in the game until it's 2 players left.\n" + \
            "You are player number " + str(player_num);
    if (role == 3):
        inst += " and you are Mr. White, so you are not given a word.";
    else:
        inst += " and your word is " + ((undercover_word) if role == 2 else (civilian_word)) + ", but you are not given information if you are a Civilian or Undercover. ";
    inst += "This is the " + turn_word(turn_count) + " turn" + (" and the context of the previous turns is:\n" if len(context) > 0 else ".");
    if (len(context) > 0):
        inst += context_string(context, player_num);
    return inst;
##
def get_full_prompt(i, vote, context_ex = True):
    if (player_count > 3 or (player_count == 3 and not mrwhite_included)):
        instruction = get_instruction(i, roles[i], turn, context if context_ex else {});
        prompt = get_input(vote);
        return instruction, prompt;
    else:
        print("ERROR: Invalid player count."); sys.stdout.flush(); sys.exit(1);
####

# Test prompt
#context = {-1: { 1: "3"},  1: {1: "Tail", 2: "Sneaky", 3: "Energetic"}, 2: {1: "Small"}}
#print(get_instruction_3(2, True, 2, context));


def prompt_client(client_number, instruction, prompt):
    if (full_debug):
        print("-- Asking client " + str(client_number) + " the following:\n~~~~~~~~~~");
        print(instruction)
        print(prompt)
        print("~~~~~~~~~~");
    completion = clients[client_number - 1].chat.completions.create(
      model="deepseek/deepseek-prover-v2:free",
      messages=[
        {
          "role": "user",
          "content": (instruction + "\n" + prompt)
        }
      ]
    )
    if (completion.choices == None):
        if (pause_between): input("Failure to get response, will retry. [Paused, enter to continue]");
        response = prompt_client(client_number, instruction, prompt);
    else:
        response = completion.choices[0].message.content;
        print("Response:\n----------");
        print(response);
        print("----------");
    return response;
def process_response(response, vote):
    if (not vote):
        out_list = re.findall(r'\w+', response);
        if (full_debug): print(str(response) + "\n->\n" + str(out_list));
        if (len(out_list) <= 2):
            if (len(out_list) == 1): response = out_list[0];
            elif (len(out_list) == 2): response = (out_list[0] + " " + out_list[1]);
            print(f"-- Detected response: '{response}'");
            check = input("Correctly detected? (blank for yes, otherwise no)");
        else:
            print("-- Response not valid...");
            check = "1";
        if (check == ""): return response, True;
        else:
            check = input("Actual answer (blank for retry):");
            if (check == ""): return None, False;
            return check, True;
    else:
        out_list = [int(s) for s in re.findall(r'\b\d+\b', response)];
        if (full_debug): print(str(response) + "\n->\n" + str(out_list));
        if (len(out_list) != 1): return None, False;
        response = int(out_list[0]);
        print(f"-- Detected response: '{response}'");
        check = input("Correctly detected? (blank for yes, otherwise no)");
        if (check == ""): return int(response), True;
        else:
            check = int(input("Actual answer (blank for retry):"));
            if (check == ""): return None, False;
            return int(check), True;
    return output, False


# Create agents
clients = [];
if (not manual_enter_output):
    for i in range(player_count):
        clients.append(OpenAI(
              base_url="https://openrouter.ai/api/v1",
              api_key=os.environ.get("OPENAI_API_KEY")
        ));

# TEST
"""
turn = 1;
instruction, prompt = get_full_prompt(1, True, False);
response = prompt_client(1, instruction, prompt);
valid = process_response(response, True);
"""

# Run game
turn = 1;
context = {};
context[-1] = {};
context_ex = False;
words_said = [];
if (manual_enter_output):
    print("---- Utilities:");
    print("-- Multiple words were said: ");
    print("You must say only one word.");
    print("-- Word was already said before: ");
    print("That word was already said before by another player, which you can see in the explained context, please say another word.");
    print();
print("---- STARTING GAME:");
print("Chosen words are:");
print(f"    Civilians:  {civilian_word}");
print(f"    Undercover: {undercover_word}");
print();
print(game_state_string());
print();
while (check_victory(roles) == -1):
    if (pause_between): input("[Paused, enter to continue]");
    print(f"--- Turn {turn}:");
    context[turn] = {};
    # Say word
    first_passed = False;
    for i in range(1, player_count + 1):
        # if still in game
        if (roles[i] > 0):
            if (pause_between and first_passed): input("[Paused, enter to continue]");
            if (not first_passed): first_passed = True;
            instruction, prompt = get_full_prompt(i, False, context_ex);
            if (manual_enter_output):
                print(f"-- Prompt for player {i} (" + role_text(roles[i]) + "):");
                print(instruction);
                print(prompt);
                pyperclip.copy(instruction + "\n" + prompt);
                print("-- Enter answer (single word):");
                output = input("");
            else:
                print(f"-- Prompting player {i}...");
                # Ask client again until given a good answer
                response = prompt_client(i, instruction, prompt);
                output, valid = process_response(response, False);
                while (not valid):
                    print("-- Failure to get answer, retrying...");
                    response = prompt_client(i, instruction, prompt);
                    output, valid = process_response(response, False);
                print(f"-> Detected answer: '{output}'");
            context[turn][i] = output;
            words_said.append(output);
            if (not context_ex): context_ex = True;
    print("-- Turn 1 words over, current game state:");
    print(context_string(context, -1, True));
    # Vote
    votes = [];
    for i in range(1, player_count + 1):
        # if still in game
        if (roles[i] > 0):
            if (pause_between): input("[Paused, enter to continue]");
            instruction, prompt = get_full_prompt(i, True);
            if (manual_enter_output):
                print(f"-- Prompt for player {i} (" + role_text(roles[i]) + "):");
                print(instruction);
                print(prompt);
                pyperclip.copy(instruction + "\n" + prompt);
                print("\n\nYour answer (integer):");
                output = int(input(""));
            else:
                print(f"-- Prompting player {i}...");
                # Ask client again until given a good answer
                response = prompt_client(i, instruction, prompt);
                output, valid = process_response(response, True);
                while (not valid):
                    print("-- Can't detect requested content in response, enter blank to retry or enter the answer manually:");
                    manual = input("");
                    if (manual == ""):
                        response = prompt_client(i, instruction, prompt);
                    else:
                        response = manual;
                    response = re.search('[0-9]+', response).group();
                    output, valid = process_response(response, True);
                print(f"-> Detected answer: '{output}'");
            votes.append(output);
    # Kick a player
    player_votes = [0 for i in range(player_count)]
    for vote in votes:
        if (roles[vote] > 0):
            player_votes[vote - 1] += 1;
    print("-- Voting over, results:");
    max_votes = 0; max_choices = [];
    for i in range(len(player_votes)):
        #print("Player " + str(i + 1) + ": " + str(player_votes[i]));
        if (player_votes[i] > max_votes):
            max_votes = player_votes[i]; max_choices = [i + 1];
        elif (player_votes[i] == max_votes):
            max_choices.append(i + 1);
    for i in range(player_count):
        if (roles[i + 1] > 0):
            print(f"    Player {i + 1}: {player_votes[i]}")
    # Multiple voted the max amount
    if (len(max_choices) > 1):
        voted_out = -1;
        #voted_out = random.choice(max_choices);  # -> randomly kick one of them
    else:
        voted_out = max_choices[0];
    kick_player(voted_out);
    # Turn over
    turn += 1;
    print(game_state_string());
    print();

victor = check_victory(roles);
if (victor == 3):
    print("Mr. White survived long enough, the game is over!");
    print("---- MR. WHITE WINS ----");
elif (victor == 2):
    print("The Undercover survived long enough, the game is over!");
    print("---- UNDERCOVER WIN ----");
elif (victor == 1):
    print("The Civilians are the only ones remaining, the game is over!");
    print("---- CIVILIANS WIN ----");
input("Press enter to exit...");
sys.exit(0)
