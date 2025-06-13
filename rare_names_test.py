import pandas as pd
import altair as alt

def parse_csv(file):
    data = pd.read_csv(file, sep=';')
    data["annais"] = pd.to_numeric(data["annais"], errors='coerce')
    data["dpt"] = pd.to_numeric(data["annais"], errors='coerce')
    data["sexe"] = pd.to_numeric(data["sexe"], errors='coerce').apply(lambda x: 'M' if x == 1 else 'F')
    data["nombre"] = pd.to_numeric(data["nombre"], errors='coerce').apply(int)
    return data