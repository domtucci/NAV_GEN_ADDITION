import pandas as pd
import json
import PySimpleGUI as sg
import re

def extract_conditions_from_csv(csv_path):
    df = pd.read_csv(csv_path)
    text_rows = df[df['Name'] == 'Document']['Text Area 1'].tolist()

    pattern_cwi_block = r'CWI:\s+([\w.-]+)(.+?)(?=\s*CWI:|$)'
    pattern_loop_index = r'(\w+)\s+loop_index\s+([=<>!]+)\s+(\d+)'
    pattern_context_var = r'"(\w+)"\s*([=<>!]+|in|not in)\s*(?:\[([\'\w\s,]+)\]|\'([\w\s]+)\')'
    pattern_and_or_condition = r'(\w+)\s+(OR|AND)\s+\[(.+)\]'
    pattern_not_equal_condition = r"(\w+)\s+!=\s+'(.+?)'"
    pattern_or_and_notequal = r"(\w+)\s+(OR|AND)!=\s+\[([\'\w\s,]+)\]"


    conditions_map = {}
    cwi_counts = {}  # Count dictionary for each CWI

    for text_entry in text_rows:
        cwi_matches = re.finditer(pattern_cwi_block, text_entry, re.DOTALL)

        for match in cwi_matches:
            cwi_name = match.group(1).strip()

            # Increment the count for the current CWI
            cwi_counts[cwi_name] = cwi_counts.get(cwi_name, 0) + 1

            # Append index if this CWI has multiple instances
            modified_cwi_name = f"{cwi_name}_{cwi_counts[cwi_name]}" if cwi_counts[cwi_name] > 1 else cwi_name

            and_or_condition_matches = re.finditer(pattern_and_or_condition, match.group(0))
            loop_index_matches = re.finditer(pattern_loop_index, match.group(0))
            context_matches = re.finditer(pattern_context_var, match.group(0))
            not_equal_condition_matches = re.finditer(pattern_not_equal_condition, match.group(0))
            or_notequal_matches = re.finditer(pattern_or_and_notequal, match.group(0))
            conditions = []

            for cond_match in loop_index_matches:
                question, operation, value = cond_match.groups()
                condition = {
                    'operation': operation,
                    'args': [
                        {
                            'question': question,
                            'attribute': 'loop_index'
                        },
                        int(value)
                    ]
                }
                index_number = extract_index_number(match.group(0))  # Extract INDEX from the matched CWI block
                if index_number:
                    condition['index'] = index_number
                conditions.append(condition)

            for cond_match in context_matches:
                context, operation, list_values, singular_value = cond_match.groups()

                if list_values:  # if it's a list
                    values = [v.strip(" '") for v in list_values.split(',')]
                    condition = {
                        'operation': operation,
                        'args': [
                            {
                                'context': context,
                            },
                            values  # directly set the list as the second argument
                        ]
                    }
                    conditions.append(condition)
                else:
                    condition = {
                        'operation': operation,
                        'args': [
                            {
                                'context': context,
                            },
                            singular_value
                        ]
                    }
                    conditions.append(condition)  

            for match in and_or_condition_matches:
                question = match.group(1)
                operation = match.group(2).lower()  # Convert "OR" or "AND" to lowercase
                answers = match.group(3).split(',')
                condition = {
                    "operation": operation,
                    "args": [{"question": question, "answer": answer.strip().strip("'")} for answer in answers]
                }
                conditions.append(condition) 
            
            for match in not_equal_condition_matches:
                variable = match.group(1)
                value = match.group(2)
                condition = {
                    "operation": "!=",
                    "args": [
                        {"question": variable},
                        value
                    ]
                }
                conditions.append(condition) 

            for match in or_notequal_matches:
                question = match.group(1)
                operation = match.group(2)  # Captures either "OR" or "AND"
                answers = [ans.strip().strip("'") for ans in match.group(3).split(',')]
                condition_args = [{"operation": "!=", "args": [{"question": question, "answer": answer}]} for answer in answers]
                condition = {
                    "operation": operation.lower(),  # Use the captured operation in lowercase
                    "args": condition_args
                }
                conditions.append(condition) 


            # Merging or appending the found conditions to the conditions_map
            if conditions:
                conditions_map[modified_cwi_name] = conditions

    return conditions_map

def extract_index_number(condition_key):
    # Extracts the index number from keys like 'AR-10_2'
    parts = condition_key.split('_')
    if len(parts) > 1 and parts[-1].isdigit():
        return int(parts[-1])
    return None

def integrate_conditions_into_json(json_structure, conditions_map):
    for outcome in json_structure['outcomes']:
        outcome_name = str(outcome.get('name'))  # Convert outcome name to string
        
        indexed_conditions = {}  # Format: {1: [cond1, cond2], 2: [cond3, cond4]}
        general_conditions = []

        for condition_key, conditions in conditions_map.items():
            base_name = condition_key.split('_')[0]
            
            # Adjusting the comparison for outcomes
            if outcome_name.startswith(base_name):
                index_number = extract_index_number(condition_key)
                if index_number is not None:
                    indexed_conditions.setdefault(index_number, []).extend(conditions)
                else:
                    general_conditions.extend(conditions)
        
        if 'definitions' in outcome:
            for idx, definition in enumerate(outcome['definitions']):
                idx += 1  # Adjusting since index starts from 1 in the condition map
                if 'conditions' not in definition:
                    definition['conditions'] = []

                if idx in indexed_conditions:
                    for condition in indexed_conditions[idx]:
                        if condition not in definition['conditions']:
                            definition['conditions'].append(condition)
                else: 
                    for condition in general_conditions:
                        if condition not in definition['conditions']:
                            definition['conditions'].append(condition)
        else:
            if 'conditions' not in outcome:
                outcome['conditions'] = []

            for condition in general_conditions:
                if condition not in outcome['conditions']:
                    outcome['conditions'].append(condition)

    return json_structure

def main():
    sg.theme('DarkTeal2')

    layout = [[sg.T("")],
                [sg.Text("Upload the WIREFRAME CSV File: "), sg.Input(key="csv_path"), sg.FileBrowse(key="file_path_browse_csv")],
                [sg.Text('Upload the JSON version of the INTERPRETATION File: '), sg.Input(key='JSON_path'), sg.FileBrowse(key="file_path_browse_interp")],
                [sg.T("")],
                [sg.Button("Submit", bind_return_key=True), sg.Button('Cancel')]]

    window = sg.Window('Main Menu', layout, size=(800, 250))

    while True:
        event, values = window.Read()
        if event == sg.WIN_CLOSED or event == 'Cancel':
            break
        elif event == 'Submit':
            interp_file_path = values['JSON_path']
            csv_file_path = values['csv_path']

            conditions = extract_conditions_from_csv(csv_file_path)
            print("Conditions map:", conditions)

            with open(interp_file_path, 'r') as jsonfile:
                data = json.load(jsonfile)

            updated_data = integrate_conditions_into_json(data, conditions)

            new_file_path = interp_file_path.replace('.json', '_updated.json')
            with open(new_file_path, 'w') as outfile:
                json.dump(updated_data, outfile, indent=4)

            sg.Popup(f"Successfully added conditions to the JSON file! New file saved as {new_file_path}")
            window.close()

if __name__ == '__main__':
    main()
