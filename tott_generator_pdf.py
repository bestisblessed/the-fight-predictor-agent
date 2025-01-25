import pandas as pd
import shutil
import matplotlib.pyplot as plt

shutil.copy('../mma-ai/Scrapers/data/fighter_info.csv', 'data/')
shutil.copy('../mma-ai/Scrapers/data/event_data_sherdog.csv', 'data/')

file_path = 'data/fighter_info.csv'
fighter_data = pd.read_csv(file_path)

fighter1_name = 'Dan Hooker'
fighter2_name = 'Justin Gaethje'

# Function to retrieve fighter info from CSV
def get_fighter_info(name):
    name = name.lower()
    fighter_info = fighter_data[fighter_data['fighter'] == name]
    if fighter_info.empty:
        return None
    return fighter_info.iloc[0]

fighter1_info = get_fighter_info(fighter1_name)
fighter2_info = get_fighter_info(fighter2_name)

if fighter1_info is None or fighter2_info is None:
    raise ValueError("One or both fighters not found in the dataset.")

fighter1_stats = {
    'Weight Class': fighter1_info['weight class'],
    'Wins': fighter1_info['wins'],
    'Losses': fighter1_info['losses'],
    'Win Streak': fighter1_info['current_win_streak'],
    'Recent Win Rate (5 fights)': fighter1_info['recent_win_rate_5fights'],
    'Height': fighter1_info['height'],
    'Reach': fighter1_info['reach']
}

fighter2_stats = {
    'Weight Class': fighter2_info['weight class'],
    'Wins': fighter2_info['wins'],
    'Losses': fighter2_info['losses'],
    'Win Streak': fighter2_info['current_win_streak'],
    'Recent Win Rate (5 fights)': fighter2_info['recent_win_rate_5fights'],
    'Height': fighter2_info['height'],
    'Reach': fighter2_info['reach']
}

# Prepare data for table
headers = ["Metric", fighter1_name, fighter2_name]
metrics = list(fighter1_stats.keys())

cell_data = []
for metric in metrics:
    cell_data.append([
        metric,
        str(fighter1_stats[metric]),
        str(fighter2_stats[metric])
    ])

# Create a matplotlib figure to hold the table
fig, ax = plt.subplots(figsize=(8, 6))

# Add a title at the top
plt.suptitle(f"Tale of the Tape: {fighter1_name} vs. {fighter2_name}", fontsize=16, fontweight='bold')

# Add Fight Overview text as a smaller subtitle
plt.title(f"Fight Overview\nWeight Class: {fighter1_stats['Weight Class']} Bout", fontsize=12)

# Hide axes
ax.axis('off')

# Create the table
table = ax.table(
    cellText=cell_data,
    colLabels=headers,
    cellLoc='center',
    loc='center'
)

# Adjust table properties
table.auto_set_font_size(False)
table.set_fontsize(10)

# Layout
fig.tight_layout()

# Save the figure to PDF
output_path = f"reports/tott_{fighter1_name}_{fighter2_name}.pdf"
plt.savefig(output_path, format='pdf')
print(f"Tale of the Tape saved to PDF: {output_path}")
