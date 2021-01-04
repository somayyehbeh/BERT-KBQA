# -*- coding: utf-8 -*-
"""
Created on Sat Dec 19 22:23:21 2020

@author: meti
"""

import pandas as pd
import numpy as np 
from pytorch_pretrained_bert import BertTokenizer
from itertools import chain, combinations
from sklearn.model_selection import train_test_split

def powerset(iterable):
    power_set = chain.from_iterable(combinations(iterable, r) for r in range(len(iterable)+1))
    power_set = [list(item) for item in power_set]
    power_set = sorted(power_set, key=lambda x:len(x), reverse=True)
    power_set.remove([iterable[0], iterable[-1]])
    return power_set


def read_reverb(reverb_path):
    lines = []
    with open(reverb_path) as fin:
        for line in fin:
            temp = line.strip().split('\t')
            lines.append(temp)
    return lines

def get_triple(record_list, index):
    temp = record_list[index]
    return (temp[1], temp[2], temp[3])

def get_normalized_triple(record_list, index):
    temp = record_list[index]
    return (temp[4], temp[5], temp[6])



def combine_with_reverb(questions_path=r'data/Final_Sheet_990824.xlsx',
                   reverb_path=r'data/reverb_wikipedia_tuples-1.1.txt'):
    dataframe = pd.read_excel(questions_path, sheet_name=1, engine='openpyxl')
    dataframe = dataframe[dataframe.Meaningful==1]
    tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
    addspecialtokens = lambda string:f'[CLS] {string} [SEP]'
    wordstoberttokens = lambda string:tokenizer.tokenize(string)
    berttokenstoids = lambda tokens:tokenizer.convert_tokens_to_ids(tokens)
    dataframe['token_matrix'] = dataframe.Question.apply(addspecialtokens).apply(wordstoberttokens).apply(berttokenstoids)
    reverb = read_reverb(reverb_path)
    dataframe['triple'] = dataframe.Reverb_no.apply(lambda x:get_triple(reverb, x))
    dataframe['normalized_triple'] = dataframe.Reverb_no.apply(lambda x:get_normalized_triple(reverb, x))
    maxlen = dataframe['token_matrix'].apply(lambda x:len(x)).max()
     
    dataframe['first_entity_ids'] = dataframe['triple'].apply(lambda x:x[0]).apply(addspecialtokens).apply(wordstoberttokens).apply(berttokenstoids)
    dataframe['second_entity_ids'] = dataframe['triple'].apply(lambda x:x[-1]).apply(addspecialtokens).apply(wordstoberttokens).apply(berttokenstoids)
    dataframe['relation_ids'] = dataframe['triple'].apply(lambda x:x[1]).apply(addspecialtokens).apply(wordstoberttokens).apply(berttokenstoids)
    dataframe.to_excel("intermediate.xlsx")
    
def get_borders(bigger, smaller):
    power_set = powerset(smaller)
    for smaller_subset in power_set[:-1]:
        net_bigger = bigger[1:-1]; net_smaller = smaller_subset[1:-1]
        for i in range(1, len(net_bigger)-len(net_smaller)+1):
            if net_bigger[i:i+len(net_smaller)]==net_smaller:
                return [i+1, i+len(net_smaller)+1]
    return [-1, -1]


def create_bertified_dataset(input_excel = r'intermediate.xlsx',
                              oputput_pkl = r'bertified.npz'):
    dataframe = pd.read_excel('intermediate.xlsx', engine='openpyxl')
    maxlen = dataframe['token_matrix'].apply(lambda x:len(eval(x))).max()
    token_mat = np.zeros((len(dataframe), maxlen), dtype="int32")
    for i, row in enumerate(dataframe['token_matrix'].to_list()):
        token_mat[i, :len(eval(row))] = eval(row)
    relation_borders = np.zeros((len(dataframe), 2), dtype='int32')
    for i, (bigger, smaller) in enumerate(zip(dataframe['token_matrix'].to_list(), 
                                              dataframe['relation_ids'].to_list())):
        relation_borders[i, :] = get_borders(eval(bigger), eval(smaller))
    entity_borders = np.zeros((len(dataframe), 2), dtype='int32')
    for i, (bigger, ent1, ent2) in enumerate(zip(dataframe['token_matrix'].to_list(), 
                                           dataframe['first_entity_ids'].to_list(),
                                           dataframe['second_entity_ids'].to_list())):
        temp1 = get_borders(eval(bigger), eval(ent1))
        temp2 = get_borders(eval(bigger), eval(ent2))
        if (temp1[-1]-temp1[0])>(temp2[-1]-temp2[0]):
            entity_borders[i] = temp1
        else:
            entity_borders[i] = temp2
    dumb_samples = []
    for i, (tokens, relation, entity) in enumerate(zip(token_mat, relation_borders, entity_borders)):
        if relation[0]==relation[-1] or entity[0]==entity[-1]:
            dumb_samples.append(i)
    dumb_records = dataframe.iloc[dumb_samples, :]
    dumb_records.to_excel('dumb_records.xlsx')
    useful_records = dataframe[~(dataframe.index.isin(dumb_samples))]
    train, test = train_test_split(useful_records, test_size=0.30, random_state=42)
    train, valid = train_test_split(train, test_size=0.15, random_state=42)
    train.to_excel('train.xlsx'); valid.to_excel('valid.xlsx'); test.to_excel('test.xlsx')
    relation_borders = np.delete(relation_borders, dumb_samples, axis=0)
    entity_borders = np.delete(entity_borders, dumb_samples, axis=0)
    token_mat = np.delete(token_mat, dumb_samples, axis=0)
    # print(entity_borders.shape, token_mat.shape, entity_borders.shape)
    with open('tokenmat.npy', 'wb') as f:
        np.save(f, token_mat)
    with open('entities.npy', 'wb') as f:
        np.save(f, entity_borders)
    with open('relations.npy', 'wb') as f:
        np.save(f, relation_borders)
            
def read_data(token_path=r'\semparse\data\ours\tokenmat.npy',	
			relation_path=r'\semparse\data\ours\relations.npy', 
			entity_path=r'\semparse\data\ours\entities.npy'):
	tokens = np.load(token_path)
	relations = np.load(relation_path)
	entities = np.load(entity_path)
	labels = np.hstack((entities, relations))
	X_train, X_test, y_train, y_test = train_test_split(tokens, labels, test_size=0.30, random_state=42)
    X_train, X_valid, y_train, y_valid = train_test_split(X_train, y_train, test_size=0.15, random_state=42)
	tselected = [torch.from_numpy(X_train).long(), torch.from_numpy(y_train[:, 2:]).long()]
	vselected = [torch.from_numpy(X_valid).long(), torch.from_numpy(y_valid[:, 2:]).long()]
	xselected = [torch.from_numpy(X_test).long(), torch.from_numpy(y_test[:, 2:]).long()]
	traindata = TensorDataset(*tselected)
	devdata = TensorDataset(*vselected)
	testdata = TensorDataset(*xselected)

	ret = (traindata, devdata, testdata)
	return ret

if __name__ == '__main__':
    
    combine_with_reverb()

    create_bertified_dataset()