import asyncio  # Importar asyncio para trabalhar com temporizadores
import re  # Importar para trabalhar com expressões regulares
import discord
import random
from discord.ext import commands
from discord.ext.commands import CommandOnCooldown

# Configurações do bot
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Habilita o conteúdo das mensagens
bot = commands.Bot(command_prefix='!', intents=intents)

# Dicionário para armazenar iniciativas por canal
iniciativas = {}
# Limite de inatividade: 60 minutos
TEMPO_INATIVIDADE = 3600  # 60 minutos em segundos
inatividade_timers = {}  # Dicionário para controlar os timers de inatividade por canal

# Função para reiniciar o temporizador de inatividade da iniciativa
async def reiniciar_timer_inatividade(canal_id):
    pass
    # Cancela o temporizador atual, se houver
    if canal_id in inatividade_timers:
        inatividade_timers[canal_id].cancel()

    # Cria um novo temporizador para encerrar a iniciativa após 60 minutos de inatividade
    async def encerrar_iniciativa_por_inatividade():
        await asyncio.sleep(TEMPO_INATIVIDADE)
        if canal_id in iniciativas:
            del iniciativas[canal_id]
            inatividade_timers.pop(canal_id, None)
            print(f"Iniciativa encerrada por inatividade no canal {canal_id}")

    # Salva o novo temporizador
    inatividade_timers[canal_id] = asyncio.create_task(encerrar_iniciativa_por_inatividade())

# Lista de servidores autorizados (IDs fictícios, substitua pelos IDs reais)
authorized_guilds = [1174709151633514617, 853701648849436752]  # Insira aqui os IDs dos servidores autorizados

# Evento para sair de servidores não autorizados
@bot.event
async def on_guild_join(guild):
    if guild.id not in authorized_guilds:
        print(f"Sair do servidor '{guild.name}' (ID: {guild.id}) - não autorizado.")
        await guild.leave()

# Dicionário para armazenar iniciativas por canal
iniciativas = {}
# Limites de tempo em segundos: 10 segundos até 3 horas (10800 segundos)
TEMPO_MINIMO = 10
TEMPO_MAXIMO = 10800
temporizadores = {}  # Dicionário para armazenar temporizadores ativos por canal

# Dicionário para armazenar as macros por usuário (um dicionário dentro de outro)
macros = {}

# Função para rolar os dados com modificadores e múltiplas rolagens, agora com suporte a +, -, *, / e fudge/fate (df)
def roll_dice(dice_expression):
    dice_expression = dice_expression.lower()

    # Verifica se é uma rolagem do tipo "fudge/fate" (ex: 4df)
    if "df" in dice_expression:
        num_dice = int(dice_expression.replace("df", "").strip())  # Ex: 4df -> 4 dados fudge
        dice_size = 'fate'  # Define o tipo de dado como "fate"
        return 1, num_dice, dice_size, [], [], None, None  # Retorna 7 valores para manter consistência

    # Suporte a rolagens com guarda (keep)
    if ">" in dice_expression:
        dice_expression, threshold = dice_expression.split(">")
        threshold = int(threshold)
        keep_high = True
    elif "<" in dice_expression:
        dice_expression, threshold = dice_expression.split("<")
        threshold = int(threshold)
        keep_high = False
    else:
        threshold = None
        keep_high = None

    # Suporte a rolagens múltiplas (ex: 3#1d20)
    if "#" in dice_expression:
        num_rolls, dice_expression = dice_expression.split("#")
        num_rolls = int(num_rolls)
    else:
        num_rolls = 1

 # Dividir a expressão de modificador e dado
    dice_parts = re.split(r'(\+|\-|\*|/)', dice_expression)
    roll_part = dice_parts[0].strip()


 # Se o primeiro número não incluir um número de dados (ex: d20), adiciona 1 dado
    if roll_part.startswith('d'):
        num_dice = 1
        dice_size = int(roll_part[1:])
    else:
        num_dice, dice_size = map(int, roll_part.split('d'))

    if num_rolls > 100 or dice_size > 100 or num_dice > 1000:
        raise ValueError("Você pode rolar até 100 vezes e o dado pode ter até 100 lados.")

    modifiers = []
    operations = []

      # Processar modificadores que também podem conter rolagens de dados
    for i in range(1, len(dice_parts), 2):
        operations.append(dice_parts[i])  # Operadores como +, -, *, /
        mod = dice_parts[i + 1].strip()

        # Se o modificador for uma expressão de dados (ex: 1d6)
        if 'd' in mod:
            mod_dice, mod_size = map(int, mod.split('d'))
            mod_value = sum(random.randint(1, mod_size) for _ in range(mod_dice))
        else:
            mod_value = int(mod)  # Modificador numérico direto

        modifiers.append(mod_value)

    return num_rolls, num_dice, dice_size, modifiers, operations, threshold, keep_high


# Função para aplicar modificadores usando os operadores
def apply_modifiers(base_value, modifiers, operations):
    result = base_value
    for i in range(len(modifiers)):
        if operations[i] == '+':
            result += modifiers[i]
        elif operations[i] == '-':
            result -= modifiers[i]
        elif operations[i] == '*':
            result *= modifiers[i]
        elif operations[i] == '/':
            result = int(result / modifiers[i])  # Divisão inteira
    return result

# Função para processar rolagens com múltiplos dados ou fate (df), incluindo filtros > e <
def process_multiple_rolls(num_rolls, num_dice, dice_size, modifiers, operations, threshold=None, keep_high=None):
    total_rolls = []
    
    for _ in range(num_rolls):
        if dice_size == 'fate':  # Rolagem de dados fudge/fate (df)
            rolls = [random.choice([-1, 0, +1]) for _ in range(num_dice)]
        else:
            rolls = [random.randint(1, dice_size) for _ in range(num_dice)]
        
        # Ordena os resultados e aplica o threshold para pegar os maiores ou menores no total
        if threshold is not None:
            kept_rolls = sorted(rolls, reverse=keep_high)[:threshold]  # Ordena e pega os 'threshold' maiores ou menores
        else:
            kept_rolls = rolls

        total = apply_modifiers(sum(kept_rolls), modifiers, operations)
        total_rolls.append((total, rolls, modifiers))  # Passa todos os rolls para mostrar no embed
    
    return total_rolls

# Função para formatar os resultados, destacando críticos (máximo) e desastres (mínimo)
def format_rolls(rolls, dice_size):
    formatted_rolls = []
    if dice_size == 'fate':  # Formatação especial para dados fudge/fate
        symbols = {-1: "-", 0: "0", +1: "+"}
        formatted_rolls = [symbols[roll] for roll in rolls]
    else:
        for roll in rolls:
            if roll == 1:
                formatted_rolls.append(f"`{roll}`")  # Desastre (mínimo)
            elif roll == dice_size:
                formatted_rolls.append(f"`{roll}`")  # Crítico (máximo)
            else:
                formatted_rolls.append(str(roll))
    return ", ".join(formatted_rolls)

# Função para enviar os resultados no formato correto para rolagens do tipo N#dX
async def send_embed_ndx(ctx, dice, total_rolls, dice_size, modifiers, operations):
    embed = discord.Embed(title="Resultado da Rolagem", description=f"Você rolou {dice}", color=discord.Color.dark_grey())

    # Ajuste para exibir as rolagens e os totais em uma linha só
    all_rolls = []
    all_totals = []

    for total, rolls, _ in total_rolls:
        all_rolls.extend(rolls)  # Adiciona todas as rolagens
        all_totals.append(f"`{total}`")  # Adiciona o total com a formatação de código (caixa preta)

    # Se existirem modificadores, exibe-os de forma concatenada
    mod_str = " ".join([f"{operations[j]} {modifiers[j]}" for j in range(len(modifiers))]) if modifiers else "Nenhum"

    # Mensagem formatada com quebras de linha para cada título
    result_message = (f"**⚔️ Rolagem:**\n"
                      f"**Dados Rolados:**\n{', '.join(map(str, all_rolls))}\n\n"  # Quebra de linha após o título
                      f"**Modificadores:**\n{mod_str}\n\n"  # Quebra de linha após o título
                      f"**Total:**\n{', '.join(all_totals)}")  # Quebra de linha após o título

    embed.add_field(name="Resultado", value=result_message, inline=False)
    await ctx.send(embed=embed)

# Função para enviar o embed padrão para outros tipos de rolagem
async def send_embed(ctx, dice, total_rolls, dice_size, modifiers, operations):
    embed = discord.Embed(title="Resultado da Rolagem", description=f"Você rolou {dice}", color=discord.Color.dark_grey())

    for i, (total, rolls, _) in enumerate(total_rolls, 1):
        formatted_rolls_str = format_rolls(rolls, dice_size)
        mod_str = " ".join([f"{operations[j]} {modifiers[j]}" for j in range(len(modifiers))]) if modifiers else "Nenhum"
        highlighted_total = f"`{highlight_total(total, dice_size)}`"  # Adiciona o total com formatação de código

        # Mensagem formatada com quebras de linha para cada título
        result_message = (f"**⚔️ Rolagem {i}:**\n"
                          f"**Dados Rolados:**\n{formatted_rolls_str}\n\n"  # Quebra de linha após o título
                          f"**Modificadores:**\n{mod_str}\n\n"  # Quebra de linha após o título
                          f"**Total:**\n{highlighted_total}")  # Quebra de linha após o título

        embed.add_field(name=f"Resultado {i}", value=result_message, inline=False)

    await ctx.send(embed=embed)

# Comando para rolar os dados
@bot.command(aliases=['R'])
@commands.cooldown(5, 30, commands.BucketType.user)  # Throttle e rate limit
async def r(ctx, dice: str):
    try:
        # Realiza o processamento da rolagem
        num_rolls, num_dice, dice_size, modifiers, operations, keep, keep_high = roll_dice(dice)

        # Verifica o número de dados para ajustar o comportamento
        if dice_size == 'fate':  # Tratamento especial para dados fudge/fate
            total_rolls = process_multiple_rolls(num_rolls, num_dice, dice_size, modifiers, operations)
        elif num_dice == 1:  # Quando o número de dados é 1 (ex: 3#1d20)
            total_rolls = process_multiple_rolls(num_rolls, 1, dice_size, modifiers, operations, keep, keep_high)
        else:  # Quando o número de dados é maior que 1 (ex: 3d20)
            total_rolls = process_multiple_rolls(num_rolls, num_dice, dice_size, modifiers, operations, keep, keep_high)

        # Modificar a expressão para aceitar qualquer valor de dado de d2 até d100
        if re.match(r"^\d+#d([2-9]|[1-9]\d|100)", dice):  # Verifica se o comando é N#dX (onde X pode ser de d2 até d100)
            await send_embed_ndx(ctx, dice, total_rolls, dice_size, modifiers, operations)
        else:
            await send_embed(ctx, dice, total_rolls, dice_size, modifiers, operations)

    except CommandOnCooldown as e:
        await ctx.send(f"Você está rolando muito rápido! Tente novamente em {e.retry_after:.2f} segundos.")
    except ValueError as e:
        await ctx.send(f"Erro: {str(e)}. Use o formato correto, como 1d20+5, 3#1d20 ou 4df.")
    except Exception as e:
        await ctx.send(f"Erro inesperado: {str(e)}")

# Exemplo de implementação da função highlight_total para garantir que ela funcione corretamente
def highlight_total(total, dice_size):
    # Aqui pode haver lógica específica para destacar os totais conforme o tamanho do dado
    return f"**{total}**"

# Função para destacar o total com caixa preta
def highlight_total(total, dice_size):
    return f"`{total}`"  # Apenas a caixa preta sem os asteriscos

# Função para dividir o texto em blocos menores se ultrapassar o limite de 1024 caracteres
def chunk_text(text, limit=1024):
    chunks = []
    while len(text) > limit:
        split_point = text.rfind(", ", 0, limit)
        if split_point == -1:
            split_point = limit
        chunks.append(text[:split_point])
        text = text[split_point:].lstrip(", ")
    chunks.append(text)
    return chunks



# Comando para calcular dano, suportando !c e !C
@bot.command(aliases=['C'])
async def c(ctx, *, expression: str):
    try:
        # Avalia a expressão matemática
        result = eval(expression)
        
        # Cria o embed com fundo igual ao do dado
        embed = discord.Embed(title="Resultado do Cálculo", 
                              description=f"Expressão: {expression}\nResultado: `{result}`",  # Caixa preta ao redor do resultado
                              color=discord.Color.dark_grey())
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"Erro ao calcular a expressão: {str(e)}")



# Comando para criar uma macro
@bot.command(name='macro')
async def create_macro(ctx, nome: str, *, dado: str):
    user_id = ctx.author.id
    if user_id not in macros:
        macros[user_id] = {}

    macros[user_id][nome] = dado
    
    # Cria embed para resposta
    embed = discord.Embed(
        title="Macro Criada",
        description=f"Macro **{nome}** criada com sucesso!",
        color=discord.Color.dark_grey()
    )
    await ctx.send(embed=embed)

# Comando para listar as macros de um usuário
@bot.command(name='lista')
async def list_macros(ctx):
    user_id = ctx.author.id
    if user_id not in macros or not macros[user_id]:
        embed = discord.Embed(
            title="Macros Salvas",
            description="Você não tem macros salvas.",
            color=discord.Color.dark_grey()
        )
        await ctx.send(embed=embed)
        return

    macro_list = "\n".join([f"{nome}: {dado}" for nome, dado in macros[user_id].items()])
    
    # Cria embed para resposta
    embed = discord.Embed(
        title="Macros Salvas",
        description=f"**Macros:**\n{macro_list}",
        color=discord.Color.dark_grey()
    )
    await ctx.send(embed=embed)

# Comando para remover uma macro de um usuário
@bot.command(name='remover')
async def remove_macro(ctx, nome: str):
    user_id = ctx.author.id
    if user_id not in macros or nome not in macros[user_id]:
        embed = discord.Embed(
            title="Erro",
            description=f"Macro **{nome}** não encontrada.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    del macros[user_id][nome]
    
    # Cria embed para resposta
    embed = discord.Embed(
        title="Macro Removida",
        description=f"Macro **{nome}** removida com sucesso!",
        color=discord.Color.dark_grey()
    )
    await ctx.send(embed=embed)



# Modal para adicionar jogador com nome, dados e vida
class AddPlayerModal(discord.ui.Modal, title="Adicionar"):
    nome = discord.ui.TextInput(label="Nome do Jogador", placeholder="Digite o nome do jogador")
    valor = discord.ui.TextInput(label="Dado e Modificador", placeholder="Ex: 1d20+5")
    vida = discord.ui.TextInput(label="Vida do Jogador", placeholder="Digite a vida total do jogador")

    def __init__(self, canal_id):
        super().__init__()
        self.canal_id = canal_id

    async def on_submit(self, interaction: discord.Interaction):
        await add_player(interaction, self.nome.value, self.valor.value, self.vida.value)

# Modal para editar jogador com nome, vida e rolagem
class EditPlayerModal(discord.ui.Modal, title="Editar"):
    nome = discord.ui.TextInput(label="Nome do Jogador", placeholder="Digite o nome do jogador")
    vida = discord.ui.TextInput(label="Nova Vida do Jogador", placeholder="Digite a nova vida do jogador")
    valor = discord.ui.TextInput(label="Novo Dado e Modificador", placeholder="Ex: 1d20+5", required=False)

    def __init__(self, canal_id):
        super().__init__()
        self.canal_id = canal_id

    async def on_submit(self, interaction: discord.Interaction):
        await edit_player(interaction, self.nome.value, self.vida.value, self.valor.value)

# Modal para remover jogador com nome
class RemovePlayerModal(discord.ui.Modal, title="Remover"):
    nome = discord.ui.TextInput(label="Nome do Jogador", placeholder="Digite o nome do jogador a ser removido")

    def __init__(self, canal_id):
        super().__init__()
        self.canal_id = canal_id

    async def on_submit(self, interaction: discord.Interaction):
        await remove_player(interaction, self.nome.value)

# Classe que define os botões para interagir com a iniciativa
class IniciativaView(discord.ui.View):
    def __init__(self, canal_id):
        super().__init__(timeout=None)
        self.canal_id = canal_id

    @discord.ui.button(label="Adicionar", style=discord.ButtonStyle.green)
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddPlayerModal(self.canal_id))  # Exibe o modal para adicionar jogador

    @discord.ui.button(label="Próximo", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await proximo(interaction)

    @discord.ui.button(label="Editar", style=discord.ButtonStyle.gray)
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditPlayerModal(self.canal_id))  # Exibe o modal para editar jogador

    @discord.ui.button(label="Remover", style=discord.ButtonStyle.red)
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RemovePlayerModal(self.canal_id))  # Exibe o modal para remover jogador

    @discord.ui.button(label="Parar", style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await parar(interaction)

# Função para destacar o jogador da vez
def formatar_jogadores(jogadores, vez_jogador):
    """Formata a lista de jogadores destacando o jogador da vez, incluindo ícones de dado e vida."""
    jogadores_formatados = []
    for jogador in jogadores:
        nome, roll, total, vida = jogador
        # **Destaque para o jogador da vez com fundo preto simples e ícones**
        if nome == vez_jogador:
            jogadores_formatados.append(f"```{nome}: 🎲 Total {total}, 🩸 Vida {vida}```")  # Destaque com bloco simples (fundo preto) e ícones
        else:
            jogadores_formatados.append(f"{nome}: 🎲 Total {total}, 🩸 Vida {vida}")
    return "\n".join(jogadores_formatados)

# Comando para iniciar uma nova iniciativa, vinculada ao canal específico
@bot.command(name='iniciativa')
async def iniciativa(ctx):
    canal_id = ctx.channel.id

    if canal_id in iniciativas:
        await ctx.send("Já existe uma iniciativa ativa neste canal!")
        return

    iniciativas[canal_id] = {
        'jogadores': [],  # Cada jogador será uma tupla (nome, rolagem, total, vida)
        'vez_jogador': 0,
        'dono': ctx.author.id,
        'ativa': True
    }

    embed = discord.Embed(
        title="🎲 Nova Iniciativa Iniciada",
        description="Adicione jogadores com os botões.",
        color=discord.Color.dark_grey()
    )

    # Cria uma interface com botões
    view = IniciativaView(canal_id)
    await ctx.send(embed=embed, view=view)

    # Reinicia o temporizador de inatividade
    await reiniciar_timer_inatividade(canal_id)

# Função para adicionar jogadores à iniciativa
async def add_player(interaction, nome, valor, vida):
    canal_id = interaction.channel_id

    if canal_id not in iniciativas:
        await interaction.response.send_message("Não há uma iniciativa ativa neste canal. Use !iniciativa para começar.", ephemeral=True)
        return

    try:
        # Se o valor for um número específico, usar diretamente
        if valor.isdigit():
            total = int(valor)
            roll = None
        else:
            roll, total = roll_iniciativa(valor)  # Calcula o valor da rolagem de dados

        iniciativa = iniciativas[canal_id]
        if any(jogador[0] == nome for jogador in iniciativa['jogadores']):
            await interaction.response.send_message(f"{nome} já está na iniciativa.", ephemeral=True)
            return

        iniciativa['jogadores'].append((nome, roll, total, int(vida)))

        # Ordena os jogadores pela rolagem mais alta
        jogadores_ordenados = sorted(iniciativa['jogadores'], key=lambda x: x[2], reverse=True)
        iniciativa['jogadores'] = jogadores_ordenados

        vez_jogador = iniciativa['jogadores'][iniciativa['vez_jogador']][0]  # Jogador atual
        embed = discord.Embed(
            title=f"✅ {nome} foi adicionado à iniciativa!",
            description=f"🎲 Total: {total}, 🩸 Vida: {vida}\n\n**Iniciativa Atual:**\n" +
                        formatar_jogadores(jogadores_ordenados, vez_jogador),
            color=discord.Color.green()
        )

        view = IniciativaView(canal_id)  # Inclui os botões novamente
        await interaction.response.send_message(embed=embed, view=view)

        # Reinicia o temporizador de inatividade
        await reiniciar_timer_inatividade(canal_id)

    except ValueError as e:
        await interaction.response.send_message(f"Erro: {str(e)}. Use o formato correto: nome, vida e 1d20+modificador.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Erro inesperado: {str(e)}", ephemeral=True)

# Função para editar um jogador existente
async def edit_player(interaction, nome, vida, valor=None):
    canal_id = interaction.channel_id

    if canal_id not in iniciativas:
        await interaction.response.send_message("Não há uma iniciativa ativa neste canal.", ephemeral=True)
        return

    iniciativa = iniciativas[canal_id]
    jogadores = iniciativa['jogadores']

    for i, jogador in enumerate(jogadores):
        if jogador[0] == nome:
            jogadores[i] = (nome, jogador[1], int(valor) if valor else jogador[2], int(vida))
            iniciativa['jogadores'] = jogadores

            vez_jogador = iniciativa['jogadores'][iniciativa['vez_jogador']][0]
            embed = discord.Embed(
                title=f"✅ {nome} foi atualizado!",
                description=f"🎲 Total: {jogadores[i][2]}, 🩸 Vida: {vida}\n\n**Iniciativa Atual:**\n" +
                            formatar_jogadores(jogadores, vez_jogador),
                color=discord.Color.green()
            )

            view = IniciativaView(canal_id)
            await interaction.response.send_message(embed=embed, view=view)
            return

    await interaction.response.send_message(f"Jogador {nome} não encontrado.", ephemeral=True)

# Função para remover um jogador
async def remove_player(interaction, nome):
    canal_id = interaction.channel_id

    if canal_id not in iniciativas:
        await interaction.response.send_message("Não há uma iniciativa ativa neste canal.", ephemeral=True)
        return

    iniciativa = iniciativas[canal_id]
    jogadores = iniciativa['jogadores']

    iniciativa['jogadores'] = [jogador for jogador in jogadores if jogador[0] != nome]

    vez_jogador = iniciativa['jogadores'][iniciativa['vez_jogador']][0] if iniciativa['jogadores'] else None
    embed = discord.Embed(
        title=f"🗑️ {nome} foi removido da iniciativa.",
        description="**Iniciativa Atual:**\n" +
                    formatar_jogadores(iniciativa['jogadores'], vez_jogador) if vez_jogador else "Sem jogadores na iniciativa.",
        color=discord.Color.red()
    )

    view = IniciativaView(canal_id)
    await interaction.response.send_message(embed=embed, view=view)

# Função para editar um jogador existente
async def proximo(interaction):
    canal_id = interaction.channel_id

    if canal_id not in iniciativas:
        await interaction.response.send_message("Não há uma iniciativa ativa neste canal. Use !iniciativa para começar.", ephemeral=True)
        return

    # Deferindo a resposta para não causar o erro de "interação falhou"
    await interaction.response.defer()

    iniciativa = iniciativas[canal_id]
    jogadores = iniciativa['jogadores']

    if not jogadores:
        await interaction.followup.send("Nenhum jogador foi adicionado à iniciativa.", ephemeral=True)
        return

    iniciativa['vez_jogador'] = (iniciativa['vez_jogador'] + 1) % len(jogadores)
    vez_jogador = jogadores[iniciativa['vez_jogador']][0]  # Jogador atual

    embed = discord.Embed(
        title="➡️ Próximo Jogador",
        description=f"**Iniciativa Atualizada:**\n" +
                    formatar_jogadores(jogadores, vez_jogador),
        color=discord.Color.blue()
    )

    view = IniciativaView(canal_id)  # Inclui os botões novamente
    await interaction.followup.send(embed=embed, view=view)

    # Reinicia o temporizador de inatividade
    await reiniciar_timer_inatividade(canal_id)

# Comando para mostrar a iniciativa atual
@bot.command(name='mostrar')
async def mostrar_iniciativa(ctx):
    canal_id = ctx.channel.id

    if canal_id not in iniciativas:
        await ctx.send("Não há uma iniciativa ativa neste canal. Use !iniciativa para começar.")
        return

    iniciativa = iniciativas[canal_id]
    jogadores = iniciativa['jogadores']

    if not jogadores:
        await ctx.send("Nenhum jogador foi adicionado à iniciativa.")
        return

    vez_jogador = jogadores[iniciativa['vez_jogador']][0]  # Jogador atual

    embed = discord.Embed(
        title="📜 Iniciativa Atual",
        description="\n".join([f"{j[0]}: Total `{j[2]}`" if j[0] != vez_jogador else f"`{j[0]}: Total {j[2]}`" for j in jogadores]),
        color=discord.Color.orange()
    )

    # Inclui a view com os botões da iniciativa novamente
    view = IniciativaView(canal_id)
    await ctx.send(embed=embed, view=view)

# Função chamada pelo botão de parar iniciativa
async def parar(interaction):
    canal_id = interaction.channel_id
    user_id = interaction.user.id

    if canal_id not in iniciativas:
        await interaction.response.send_message("Não há uma iniciativa ativa neste canal.", ephemeral=True)
        return

    if iniciativas[canal_id]['dono'] != user_id:
        await interaction.response.send_message("Apenas o dono da iniciativa pode encerrá-la.", ephemeral=True)
        return

    del iniciativas[canal_id]
    embed = discord.Embed(
        title="⛔ Iniciativa Finalizada",
        description="A rodada de iniciativa foi encerrada.",
        color=discord.Color.red()
    )
    await interaction.channel.send(embed=embed)

    # Cancela o temporizador de inatividade
    if canal_id in inatividade_timers:
        inatividade_timers[canal_id].cancel()
        del inatividade_timers[canal_id]

# Função para rolar o dado com modificador para a iniciativa
def roll_iniciativa(roll_expression):
    dice_parts = re.split(r'(\+|\-)', roll_expression.lower())
    roll_part = dice_parts[0].strip()

    if 'd' not in roll_part:
        raise ValueError("Formato incorreto de dado. Use algo como 1d20+5.")

    num_dice, dice_size = map(int, roll_part.split('d'))

    if len(dice_parts) > 1:
        modifier = int(dice_parts[2].strip())
        if modifier < 0 or modifier > 1000:
            raise ValueError("O modificador deve ser entre 1 e 1000.")
    else:
        modifier = 0

    roll = sum(random.randint(1, dice_size) for _ in range(num_dice))
    total = roll + modifier

    return roll, total

# Evento para confirmar que o bot está online
@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')



# Função para formatar o tempo em minutos e segundos
def format_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

# Classe que define os botões para interagir com o temporizador
class TimerView(discord.ui.View):
    def __init__(self, canal_id):
        super().__init__(timeout=None)
        self.canal_id = canal_id

    @discord.ui.button(label="Parar Tempo", style=discord.ButtonStyle.red)
    async def stop_timer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await parart(interaction)

# Comando para iniciar um temporizador com contagem regressiva e atualização de mensagem
@bot.command(name='tempo')
async def tempo(ctx, segundos: int):
    # Verifica se já existe um temporizador no canal
    if ctx.channel.id in temporizadores:
        await ctx.send("Já existe um temporizador ativo neste canal. Use `!parart` para interrompê-lo.")
        return

    # Verifica se o valor está dentro dos limites
    if segundos < TEMPO_MINIMO or segundos > TEMPO_MAXIMO:
        await ctx.send(f"Por favor, insira um valor entre {TEMPO_MINIMO} segundos (10s) e {TEMPO_MAXIMO} segundos (3 horas).")
        return

    # Cria o embed inicial informando que o temporizador começou
    embed = discord.Embed(
        title="⏳ Temporizador Iniciado",
        description=f"Tempo restante: `{format_time(segundos)}`",
        color=discord.Color.dark_grey()
    )
    message = await ctx.send(embed=embed, view=TimerView(ctx.channel.id))  # Envia a mensagem com botões

    # Salva o temporizador
    temporizadores[ctx.channel.id] = True

    try:
        # Loop para atualizar a mensagem a cada segundo
        while segundos > 0 and temporizadores[ctx.channel.id]:
            await asyncio.sleep(1)
            segundos -= 1
            embed.description = f"Tempo restante: `{format_time(segundos)}`"
            await message.edit(embed=embed)  # Edita a mensagem com o novo tempo

        # Se o temporizador não foi interrompido, exibe a mensagem final
        if temporizadores[ctx.channel.id]:
            embed_final = discord.Embed(
                title="⏰ Tempo Esgotado!",
                description="O temporizador terminou.",
                color=discord.Color.red()
            )
            await message.edit(embed=embed_final)

        # Remove o temporizador quando acabar
        del temporizadores[ctx.channel.id]

    except asyncio.CancelledError:
        del temporizadores[ctx.channel.id]
        await ctx.send("Temporizador cancelado.")

# Função chamada pelo botão ou comando para parar o temporizador
async def parart(interaction):
    canal_id = interaction.channel_id if hasattr(interaction, 'channel_id') else interaction.channel.id

    # Verifica se há um temporizador ativo no canal
    if canal_id in temporizadores and temporizadores[canal_id]:
        temporizadores[canal_id] = False  # Define o temporizador como parado
        embed_cancelado = discord.Embed(
            title="⛔ Temporizador Interrompido",
            description="O temporizador foi interrompido.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed_cancelado)
    else:
        await interaction.response.send_message("Não há temporizador ativo neste canal.", ephemeral=True)

# Evento para confirmar que o bot está online
@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

# Iniciar o bot com o token
bot.run('')