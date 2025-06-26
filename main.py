import pandas as pd
import geopandas as gpd
import altair as alt
import os

os.makedirs('out', exist_ok=True)

def parse_csv(file):
    data = pd.read_csv(file, sep=';')
    data["annais"] = pd.to_numeric(data["annais"], errors='coerce')
    data["dpt"] = pd.to_numeric(data["dpt"], errors='coerce')
    data["sexe"] = pd.to_numeric(data["sexe"], errors='coerce').apply(lambda x: 'M' if x == 1 else 'F')
    data["nombre"] = pd.to_numeric(data["nombre"], errors='coerce').apply(int)
    
    return data.dropna()

OUTLIER_THRESHOLD = 0.03

geo_data = gpd.read_file("data/departements.geojson")

print("Parsing data")
data = parse_csv("data/dpt2020.csv")

print("Making the first visualization...")

dep_counts = data.groupby(["annais", "preusuel", "dpt"])["nombre"].sum().reset_index()

total_counts = dep_counts.groupby(["annais", "preusuel"])["nombre"].sum().reset_index()
total_counts.rename(columns = {"nombre": "total_nombre"}, inplace = True)

merged = pd.merge(dep_counts, total_counts, on=["annais", "preusuel"])
merged["proportion"] = merged["nombre"] / merged["total_nombre"]
merged = merged[merged["total_nombre"] > 1000]

idx = merged.groupby(['annais', 'dpt'])['proportion'].idxmax()
outliers = merged.loc[idx].reset_index(drop=True)
outliers = outliers[outliers["proportion"] > OUTLIER_THRESHOLD]

geo_data = geo_data[geo_data["code"].str.isnumeric()]
geo_data["dpt"] = geo_data["code"].astype(int)
merged_geo = geo_data.merge(outliers, on="dpt", how="left")

year_slider = alt.binding_range(
    min=int(merged_geo['annais'].min()),
    max=int(merged_geo['annais'].max()),
    step=1,
    name='Year: '
)
year_select = alt.selection_point(
    fields=['annais'],
    bind=year_slider,
    value=[{'annais': 2020.0}]
)

base = alt.Chart(merged_geo).mark_geoshape().project(
    type='mercator'
).properties(
    width=800,
    height=400,
    title='Most Overrepresented Names by Department'
)

chart_filled = base.encode(
    color=alt.Color('preusuel:N', title='Most Overrepresented Names'),
    tooltip=[
        alt.Tooltip('nom:N', title='Department'),
        alt.Tooltip('preusuel:N', title='Name'),
        alt.Tooltip('proportion:Q', title='Proportion', format='.2%')
    ]
).add_params(
    year_select
).transform_filter(
    year_select
).transform_filter(
    'datum.preusuel != null'
)

chart_nulls = alt.Chart(geo_data).mark_geoshape().encode(
    color=alt.value('lightgrey'),
    tooltip=[]
).project(
    type='mercator'
).properties(
    width=800,
    height=400,
    title=alt.TitleParams(
        text='Most overrepresented Names by Department',
        subtitle='Regional trends and clusters',
        fontSize=20,
        subtitleFontSize=14
    )
)

chart = (chart_nulls + chart_filled).resolve_scale(
    color='independent'
)

print("Saving the first visualization...")
chart.save('out/visu1.html')
print("First visualization done!")


# =================================================================== #


print("Making the second visualization...")

data = data[data["preusuel"] != '_PRENOMS_RARES']

alt.data_transformers.disable_max_rows()
data_temp = data.copy()
data_temp["length"] = data_temp["preusuel"].str.len()
data_final = data_temp.groupby(["annais", "preusuel", "length"])["nombre"].sum().reset_index()

avg_length = data_temp.groupby("annais")["length"].mean().reset_index()
avg_length.rename(columns={"length": "avg_length"}, inplace=True)

min_overall_length = data_final['length'].min() - 0.5
max_overall_length = data_final['length'].max() + 0.5

heatmap = alt.Chart(data_final).mark_rect().encode(
    x=alt.X('annais:O', title='Year'),
    y=alt.Y('length:O', sort='descending', title='Name Length'),
    color=alt.Color('nombre:Q', scale=alt.Scale(type='log'), title='Count'),
)


line = alt.Chart(avg_length).mark_line(color='red', strokeWidth=3, interpolate='natural').encode(
    x=alt.X('annais:O'),
    y=alt.Y('avg_length:Q', title='Average Length',
            scale=alt.Scale(domain=[min_overall_length, max_overall_length]))
)

combined_chart = alt.layer(heatmap, line).properties(
    width=1500,
    height=300,
    title=alt.TitleParams(
        text='Names length heatmap and average length over time',
        fontSize=20
    )
).resolve_scale(
    x='shared'
)


print("Saving the second visualization...")
combined_chart.save('out/visu2.html')
print("Second visualization done!")

# =================================================================== #


print("Making the third visualization...")

name_counts_by_year = data.groupby(['annais', 'preusuel', 'sexe'])['nombre'].sum().reset_index()
min_year, max_year = name_counts_by_year['annais'].min(), name_counts_by_year['annais'].max()

all_years = pd.DataFrame({'annais': range(int(min_year), int(max_year) + 1)})

grouped = name_counts_by_year.groupby(['preusuel', 'sexe'])
results = []


for (name, sex), group in grouped:
    full_series = pd.merge(all_years, group, on='annais', how='left').fillna(0)

    peak_popularity = full_series['nombre'].max()
    total_births = group['nombre'].sum()
    mean_births = full_series['nombre'].mean()
    variance = full_series['nombre'].var() / (mean_births * mean_births);
    
    if pd.notna(variance) and variance > 0 and pd.notna(peak_popularity) and peak_popularity > 0:
        results.append({
            'name': name,
            'sex': sex,
            'variance': variance,
            'peak_popularity': peak_popularity,
            'total_births': total_births
        })


processed_df = pd.DataFrame(results)

avg_stats = processed_df.groupby('sex').apply(lambda d: pd.Series({
        'avg_peak_popularity': (d['peak_popularity'] * d['total_births']).sum() / d['total_births'].sum(),
        'avg_variance':        (d['variance']        * d['total_births']).sum() / d['total_births'].sum()
    }), include_groups=False).reset_index()


slider = alt.binding_range(min=processed_df['total_births'].min(), max=processed_df['total_births'].quantile(0.99), step=1000, name='Minimum Total Births:')
selector = alt.selection_point(name="Selector", fields=['cutoff'], bind=slider, value=[{'cutoff': 50000}])


base_chart = alt.Chart(processed_df).add_params(
    selector
).transform_calculate(
    filter_condition = 'datum.total_births > Selector.cutoff[0]'
).transform_filter(
    alt.datum.filter_condition
)

scatter_points = base_chart.mark_circle().encode(
    x=alt.X(
        'peak_popularity:Q',
        scale=alt.Scale(type="log", domain=[1000, 60000], nice=False),
        title='Peak Annual Popularity (More Popular →)'
    ),
    y=alt.Y(
        'variance:Q',
        scale=alt.Scale(type="linear", domain=[0, 7], nice=False),
        title='Volatility / Fad Factor'
    ),
    size=alt.Size('total_births:Q',
                scale=alt.Scale(range=[50, 2000]),
                legend=alt.Legend(title="Total births")
               ),
    color=alt.Color('sex:N',
                  scale=alt.Scale(domain=['M','F'], range=['#3b82f6','#ec4899']),
                  legend=alt.Legend(title="Sex", symbolSize=100,
                                    labelExpr="datum.label == 'M' ? 'Boy' : 'Girl'")
                 ),
    tooltip=[
        alt.Tooltip('name:N', title='Name'),
        alt.Tooltip('peak_popularity:Q', title='Peak Annual Births', format=',.0f'),
        alt.Tooltip('variance:Q', title='Volatility', format=',.0f'),
        alt.Tooltip('total_births:Q', title='Total Births', format=',')
    ]
).properties(
    width=700,
    height=500,
    title=alt.TitleParams(
        text='Popularity structures among men and women',
        subtitle='Exploring name popularity vs. volatility over time',
        fontSize=20,
        subtitleFontSize=14
    )
)

text_labels = base_chart.transform_window(
    rank_total='rank()',
    sort=[alt.SortField('total_births', order='descending')]
).transform_filter(
    alt.datum.rank_total <= 20
).mark_text(
    align='center',
    baseline='bottom',
    dy=-5,
    fontSize=10,
    fontWeight='bold',
    fill='white',
    stroke='black',
    strokeWidth=0.35 
).encode(
    x='peak_popularity:Q',
    y='variance:Q',
    text='name:N'
)

avg_points = alt.Chart(avg_stats).mark_point(
    shape='diamond',
    size=600,
    filled=True,
    opacity=1,
    stroke='black',
    strokeWidth=2  
).encode(
    x='avg_peak_popularity:Q',
    y='avg_variance:Q',
    color=alt.Color(
        'sex:N',
        scale=alt.Scale(domain=['M','F'], range=["#005ff7","#e00070"]),
        legend=None
    ),
    tooltip=[
        alt.Tooltip('sex:N', title='Sex'),
        alt.Tooltip('avg_peak_popularity:Q', title='Avg Peak Births', format=',.0f'),
        alt.Tooltip('avg_variance:Q', title='Avg Volatility', format=',.2f')
    ]
)


final_chart = (scatter_points + text_labels + avg_points).configure_view(
    stroke=None
).configure_axis(
    gridColor='grey',
    gridOpacity=0.2
).interactive()


print("Saving the third visualization...")
final_chart.save('out/visu3.html')
print("third visualization done!")