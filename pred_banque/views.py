import os
import json

from django.core.files.storage import FileSystemStorage
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
import pandas as pd
import joblib
from django.views.decorators.csrf import csrf_exempt

from .models import PredResults, BankData

# La liste des variables pertinantes de mon modèle
variable = ['Customer_Age', 'Total_Relationship_Count', 'Contacts_Count_12_mon',
            'Total_Revolving_Bal', 'Avg_Open_To_Buy', 'Total_Amt_Chng_Q4_Q1',
            'Total_Trans_Amt', 'Total_Trans_Ct', 'Total_Ct_Chng_Q4_Q1']

# Unpickle model
norm = joblib.load(r'ma_normalisation.pkl')
model = joblib.load(r"mon_modele_banque.pkl")


def predict(request):
    return render(request, 'predict.html')


def read_data():
    """Read data from Database"""
    # Ceci sont les noms des colonnes de notre base de données
    names = [col.lower() for col in variable]
    names.append('attrition_flag')
    # retourner une liste contenant par ordre les valeurs des noms de colonnes insérés
    return BankData.objects.all().values_list(*names)[:5000]


def create_df(data):
    """Create DataFrame from database"""
    col = variable
    col.append('attrition_flag')

    return pd.DataFrame(
        data,
        columns=col
    )


def view_predict_db(request, nb_page=2):
    data = create_df(read_data())
    df = data.drop('attrition_flag', axis=1)
    variable.remove('attrition_flag')
    df[variable] = norm.transform(df)
    result = model.predict(df)
    pred = pd.DataFrame(result).rename(columns={0: 'pred'})
    pred['pred'] = pred['pred'].map({0: 'Existing Customer', 1: 'Attrited Customer'})
    df = pd.concat([data, pred], axis=1)
    columns = df.columns
    if nb_page == 0:
        return render(request, "compact-table.html", context={'data': df.values, 'columns': columns})
    elif nb_page == 1:
        return render(request, "full-screen-table.html", context={'data': df.values, 'columns': columns})
    else:
        return render(request, "results_db.html", context={'data': df.values, 'columns': columns})


def predict_chances(request):
    if request.POST.get('action') == 'post':
        # return JsonResponse({'result': 'Bonjour'})
        # # if request.method == 'POST':
        # Receive data from client
        age = int(request.POST.get('age'))
        total_relationship_count = int(request.POST.get('total_relationship_count'))
        contacts_count_12_mon = int(request.POST.get('contacts_count_12_mon'))
        total_revolving_bal = int(request.POST.get('total_revolving_bal'))
        avg_open_to_buy = float(request.POST.get('avg_open_to_buy'))
        total_amt_chng_q4_q1 = float(request.POST.get('total_amt_chng_q4_q1'))
        total_trans_amt = int(request.POST.get('total_trans_amt'))
        total_trans_ct = int(request.POST.get('total_trans_ct'))
        total_ct_chng_q4_q1 = float(request.POST.get('total_ct_chng_q4_q1'))

        info = [
            age, total_relationship_count, contacts_count_12_mon, total_revolving_bal,
            avg_open_to_buy, total_amt_chng_q4_q1, total_trans_amt, total_trans_ct, total_ct_chng_q4_q1
        ]

        # return JsonResponse({'result': 'Bonjour'})

        # Make prediction
        data = pd.DataFrame(info, index=variable).T
        data[variable] = norm.transform(data)
        result = model.predict(data)
        pourcent = model.predict_proba(data)

        # On recupère la prediction
        pred = result[0]
        if pred == 0:
            classification = 'Existing Customer'
        else:
            classification = 'Attrited Customer'

        pred = PredResults(age=age, total_relationship_count=total_relationship_count,
                           contacts_count_12_mon=contacts_count_12_mon, total_revolving_bal=total_revolving_bal,
                           avg_open_to_buy=avg_open_to_buy, total_amt_chng_q4_q1=total_amt_chng_q4_q1,
                           total_trans_amt=total_trans_amt, total_trans_ct=total_trans_ct,
                           total_ct_chng_q4_q1=total_ct_chng_q4_q1, classification=classification
                           )
        pred.save()

        return JsonResponse({'result': classification, 'age': age, 'total_relationship_count': total_relationship_count,
                             'contacts_count_12_mon': contacts_count_12_mon, 'total_revolving_bal': total_revolving_bal,
                             'avg_open_to_buy': avg_open_to_buy, 'total_amt_chng_q4_q1': total_amt_chng_q4_q1,
                             'total_trans_amt': total_trans_amt, 'total_trans_ct': total_trans_ct,
                             'total_ct_chng_q4_q1': total_ct_chng_q4_q1},
                            safe=False)


def view_results(request):
    """
    Retourne l'ensemble des prédictions éffectuée sur les individus dans la page results.html
    :param request:
    :return:
    """
    # Submit prediction and show all
    data = {"dataset": PredResults.objects.all()}
    return render(request, "results.html", data)


def view_dash(request):
    """
    Affiche la page d'accueil de notre application
    :param request:
    :return:
    """
    return render(request, "page-user.html")


def upload_data(request):
    """

    :param request:
    :return: la page d'insertion du fichier csv de prédiction
    """
    return render(request, "upload_data.html")


@csrf_exempt
def affiche_data(request):
    """
    fonction qui reçoit un dictionnaire et fait des prédictions et retourne le résultat en json
    :param request:
    :return:
    """
    if request.method == "POST":
        # Je récupère le data au format json renvoyer par la requette ajax
        # puis je le transform en dictionnaire.
        data = json.loads(request.POST.get('dataset'))

        # Je transform les données en dataframe pour pouvoir extraire les variables
        # pertinantes et appliquer la normalisation
        data = pd.DataFrame(data)
        try:
            dataset = data[variable]
        except:
            return JsonResponse('Verifiéz les colonnes de vos données!', safe=False)

        else:
            # Make prediction
            dataset.loc[:, :] = norm.transform(dataset)
            result = model.predict(dataset)
            pred = pd.DataFrame(result).rename(columns={0: 'Predict'})
            pred['Predict'] = pred['Predict'].map({0: 'Existing Customer', 1: 'Attrited Customer'})
            # Ajoute la colonnes de prédiction à mon dataframe utilisé pour la prédiction
            df = pd.concat([data[variable], pred], axis=1)

            # Transformation de la reponse en json pour affichage avec ag grid
            df_json = df.T.to_json()
            df_json = json.loads(df_json)
            json_response = []

            for value in df_json.values():
                json_response.append(value)
            print(json_response)
            return JsonResponse(json_response, safe=False)
