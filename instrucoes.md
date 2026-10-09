# Algoritmo Aproximativo para Problema NP-difícil 

## Objetivo
Apresentar um algoritmo aproximativo ou uma heurística construtiva para um problema NP-difícil.

## Formato 
Pode ser utilizado o formato (template) de artigo de revista ou congresso. Recomendamos o modelo 
do  IEEE  CEC,  disponível  em:  https://ieeecec.org/2027  ou  o  modelo  da  SBC,  disponível  em: 
https://www.sbc.org.br/documentosinstitucionais/#publicacoes. Os itens exigidos seguem abaixo.

## Itens que devem constar do trabalho além de introdução, conclusão e referências bibliográficas
- Descrição do problema. 
- Complexidade do problema. 
- Heurísticas construtivas e algoritmos aproximativos já apresentados para o problema. 
- Bancos de instância (se existir). 
- Links importantes (se existir). 
- Implementação de 1 algoritmo aproximativo ou heurística construtiva. 
- Análise do algoritmo desenvolvido (complexidade em tempo e limite de aproximação, se possível). 
- Aplicação do algoritmo às instâncias encontradas na literatura. Caso não existam tais instâncias, 
criar com um gerador de instâncias. Neste caso descrever o gerador de instâncias. 
- Tabelas de resultados da aplicação do algoritmo às instâncias. Comparação com resultados de 
algoritmos publicados na literatura e discussão, se possível. 
Obs. As instâncias devem ter tamanho significativo para o problema (o tamanho vai depender do 
problema).

## entrega e outras orientações
Deve  ser  entregue  o  relatório  e  a  implementação.  Todos  os  fontes  (ou  link  para  acesso  ao 
repositório),  bem  como  conjunto  de  casos  de  teste  e  um  texto  que  permita  executar  o  algoritmo

A interface do algoritmo pode ser simples, uma vez que não será considerada na avaliação dos 
resultados. A interface deve permitir que o caso teste seja escolhido a partir do conjunto de casos 
teste e que um relatório do experimento seja apresentado na tela e salvo em arquivo. A interface 
deve permitir gravar e imprimir em tela a configuração da melhor solução, e seu valor associado 
(para conferência do acerto do algoritmo

## Tema escolhido 
O problema escolhido foi Coloração Seletiva:

Considere um conjunto de tarefas dividido em grupos distintos ou categorias, tal que é suficiente 
executar apenas uma tarefa de cada grupo, esta tarefa é dita representante do grupo. O objetivo 
é  realizar  um conjunto  suficiente  de  tarefas com o  menor  número  de  trabalhadores  possível. 
Representando cada tarefa como um vértice, categorias de tarefas como partições do conjunto 
de vértices e pares de tarefas ocorrendo no mesmo intervalo de tempo como arestas, o objetivo 
é  selecionar exatamente  uma tarefa de  cada grupo de  forma que o número de trabalhadores 
requeridos  para  completar  o  conjunto  selecionado  de  tarefas  seja  mínimo.  Quando  pegamos 
um  vértice  por  grupo  e  colorimos  os  vértices  selecionados,  cada  cor  corresponderá  a  um 
trabalhador distinto, e o conjunto de vértices coloridos com a mesma cor são tarefas que podem 
ser atribuídas ao mesmo trabalhador. Este problema tem duas etapas, a seleção dos 
representantes dos grupos e a coloração.

### Artigos relacionados
- Demange, M., Ekim, T., Ries, B., & Tanasescu, C. (2015). On some applications of the selective 
graph coloring problem. European Journal of Operational Research, 240(2), 307-314.
- Şeker, O., Ekim, T., & Taşkın, Z. C. (2021). An exact cutting plane algorithm to solve the 
selective graph coloring problem in perfect graphs. European Journal of Operational 
Research,  291(1),  67-83.  –  Este  artigo  traz  um  gerador  de  instâncias  para  o  problema  em 
grafos perfeitos.
- DEMANGE, Marc; EKIM, Tınaz; DE WERRA, Dominique. A tutorial on the use of graph 
coloring for some problems in robotics. European Journal of Operational Research, v. 192, n. 
1, p. 41-55, 2009