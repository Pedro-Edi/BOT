from datetime import datetime,timedelta
import time
import discord
from discord.ext import commands
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import View, button,Select, select

import asyncio
from aluno_banco import registrar_duvida_no_banco,registrar_aluno_no_banco,obter_duvidas_respondidas_usuario,obter_duvidas_nao_respondidas_usuario,obter_duvidas_com_resposta_nao_visualizada,atualizar_mensagens,atualizar_visualizada,deletar_duvida

duvidas_por_usuario = {}


class Aluno(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.atendimento_ativo = False # Dicionário para controlar atendimentos ativos por usuário
  
        
    # FUNÇÃO PARA QUE O USUÁRIO CONSIGA INICIAR O ATENDIMENTO
    @app_commands.command(description='Inicia o atendimento e captura as mensagens com um título definido pelo usuário.')

    async def iniciar_atendimento(self, interaction: discord.Interaction):

        # Verifica se o usuário já tem um atendimento ativo
        if self.atendimento_ativo:
            await interaction.response.send_message(
                "Você já tem um atendimento em andamento. Por favor, continue seu atendimento atual normalmente."
            )
            return
        user_name = interaction.user.name
       
        registrar_aluno_no_banco(user_name)
            
        duvidas_nao_visualizadas = obter_duvidas_com_resposta_nao_visualizada(user_name)
        await interaction.response.send_message('Bem-vindo!')
        # Notificar o usuário sobre dúvidas respondidas, mas não visualizadas
        if duvidas_nao_visualizadas:
            lista_duvidas = "\n".join([f"{index+1}️⃣ **{titulo}**" for index, titulo in enumerate(duvidas_nao_visualizadas.keys())])
            await interaction.followup.send(
                "🔔 ATENÇÃO VOCÊ TEM DÚVIDAS QUE JÁ FORAM RESPONDIDAS E NÃO VISUALIZADAS\n\n"
                f"Lista de dúvidas\n"
                f"{lista_duvidas}\n\n"
                f"Acesse o menu de visualizar dúvidas!"
            )


        self.atendimento_ativo = True

        menu_view = Menu(self.bot, self)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message 
    


class Menu(View):
    def __init__(self, bot, aluno_cog, timeout=10):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.aluno_cog = aluno_cog
        self.show_interacao = ShowInteracao(self.bot, self.aluno_cog)


    async def on_timeout(self):
        for item in self.children:
            item.disabled = True 
        if self.message: 
            await self.message.edit(content="Tempo esgotado ! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`.",view=self)
            self.aluno_cog.atendimento_ativo=False
            return
        
    async def load_filtro_duvidas(self,interaction,user_duvidas,tipo):
        menu_view = FiltroDuvidas(self.bot, self.aluno_cog,user_duvidas,tipo)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message
        
    async def load_duvidas(self,interaction):
        menu_view =  Duvidas(self.bot, self.aluno_cog)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message
        
    async def load_submenu(self,interaction):
        menu_view =  Submenu(self.bot, self.aluno_cog)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message

    async def disable_buttons_and_update(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.message=None
        
    @button(label="Adicionar dúvida", style=discord.ButtonStyle.primary)
    async def adicionar_duvida(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
        await self.show_interacao.adicionar_duvida(interaction)


    @button(label="Visualizar dúvidas", style=discord.ButtonStyle.secondary)
    async def visualizar_duvidas(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
        await self.load_duvidas(interaction)


    @button(label="Editar Dúvida", style=discord.ButtonStyle.success)
    async def editar_dúvida(self, interaction: discord.Interaction,button):
        await self.disable_buttons_and_update(interaction)
        user_name = interaction.user.name
        user_duvidas=obter_duvidas_nao_respondidas_usuario(user_name)
        await self.load_filtro_duvidas(interaction,user_duvidas,"editar")
 

    @button(label="Deletar Dúvida", style=discord.ButtonStyle.danger)
    async def deletar_duvida(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
        user_name = interaction.user.name
        user_duvidas=obter_duvidas_nao_respondidas_usuario(user_name)
        await self.load_filtro_duvidas(interaction,user_duvidas,"deletar")
     
        
class Submenu(View):
    def __init__(self, bot, aluno_cog,timeout=10):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.aluno_cog = aluno_cog

    async def disable_buttons_and_update(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.message=None


    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  
        if self.message:    
            await self.message.edit(content="Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`.",view=self)
            self.aluno_cog.atendimento_ativo=False
            return
        
    @button(label="Voltar ao menu principal", style=discord.ButtonStyle.primary)
    async def voltar_menu(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
        menu_view = Menu(self.bot, self.aluno_cog)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message

    @button(label="Finalizar atendimento", style=discord.ButtonStyle.danger)
    async def finalizar_atendimento(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
        self.aluno_cog.atendimento_ativo=False
        await interaction.followup.send("Atendimento finalizado com sucesso! Você pode iniciar um novo atendimento com o comando `/iniciar_atendimento`.")
            


class Duvidas(View):
    def __init__(self, bot, aluno_cog,timeout=10):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.aluno_cog = aluno_cog

    async def disable_buttons_and_update(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.message=None

    async def load_filtro_duvidas(self,interaction,duvidas):
        menu_view = FiltroDuvidas(self.bot, self.aluno_cog,duvidas,"visualizar")
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  
        if self.message:    
            await self.message.edit(content="Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`.",view=self)
            self.aluno_cog.atendimento_ativo=False
            return
            
    async def load_submenu(self, interaction):
        menu_view = Submenu(self.bot, self.aluno_cog)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message

    
    @button(label="Respondidas", style=discord.ButtonStyle.primary)
    async def duvidas_respondidas(self, interaction: discord.Interaction,button):
        await self.disable_buttons_and_update(interaction)
        user_name = interaction.user.name
        duvidas = obter_duvidas_respondidas_usuario(user_name)
        await self.load_filtro_duvidas(interaction,duvidas)
        
    @button(label="Não Respondidas", style=discord.ButtonStyle.secondary)
    async def duvidas_nao_respondidas(self, interaction: discord.Interaction,button):
        await self.disable_buttons_and_update(interaction) 
        user_name = interaction.user.name
        duvidas = obter_duvidas_nao_respondidas_usuario(user_name)
        await self.load_filtro_duvidas(interaction,duvidas)
        

class FiltroDuvidas(View):
    def __init__(self, bot, aluno_cog, duvidas,tipo,timeout=10):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.aluno_cog = aluno_cog
        self.duvidas=duvidas
        self.tipo=tipo
        self.show_interacao = ShowInteracao(self.bot, self.aluno_cog)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  
        if self.message:    
            await self.message.edit(content="Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`.",view=self)
            self.aluno_cog.atendimento_ativo=False
            return

    async def disable_and_update(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.message = None

    
    @select(
        placeholder="Selecione o período para filtrar as dúvidas...",
        options=[
            discord.SelectOption(label="Hoje", value="hoje", description="Dúvidas de hoje", emoji="📅"),
            discord.SelectOption(label="Últimos 7 dias", value="7_dias", description="Dúvidas dos últimos 7 dias", emoji="📆"),
            discord.SelectOption(label="Últimos 30 dias", value="30_dias", description="Dúvidas dos últimos 30 dias", emoji="🗓️"),
            discord.SelectOption(label="Todas", value="todas", description="Todas as dúvidas", emoji="🔍")
        ],
        custom_id="menu_filtro"
    )
    async def menu_filtro(self, interaction: discord.Interaction, select: Select):
        await self.disable_and_update(interaction)

        if select.values[0] == "hoje":
            inicio_periodo = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif select.values[0] == "7_dias":
            inicio_periodo = datetime.now() - timedelta(days=7)
        elif select.values[0] == "30_dias":
            inicio_periodo = datetime.now() - timedelta(days=30)
        else:
            inicio_periodo = None  


        if inicio_periodo:
            duvidas = {}

            for titulo, dados in self.duvidas.items():
                timestamp_duvida = datetime.strptime(dados["timestamp_duvida"], "%Y-%m-%d %H:%M:%S.%f")
                timestamp_resposta = (
                    datetime.strptime(dados["timestamp_resposta"], "%Y-%m-%d %H:%M:%S.%f")
                    if dados.get("timestamp_resposta") else None
                )

                if timestamp_duvida >= inicio_periodo:
                    duvidas[titulo] = {**dados, "timestamp_duvida": timestamp_duvida, "timestamp_resposta": timestamp_resposta}

        else:
            duvidas =self.duvidas


        if self.tipo=='editar':
           await self.show_interacao.show_editar_duvidas(interaction,duvidas)
        elif self.tipo=='visualizar':
            await self.show_interacao.show_duvidas(interaction,duvidas)
        elif self.tipo=='deletar':
            await self.show_interacao.show_deletar_duvidas(interaction,duvidas)



class ShowInteracao():
    def __init__(self, bot, aluno_cog):
        super().__init__()
        self.bot = bot
        self.aluno_cog = aluno_cog


    async def load_submenu(self,interaction):
        menu_view =  Submenu(self.bot, self.aluno_cog)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message

    async def gerenciar_timeout(self, interaction, timeout):
        try:
            while True:
                # Aguarda uma mensagem do usuário dentro do tempo limite
                msg = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user, timeout=timeout)
                
                # Verifica se a mensagem contém anexos (arquivos, imagens, etc.)
                if msg.attachments:
                    await interaction.followup.send(
                        "❌ **Erro:** Apenas **mensagens de texto** são permitidas. 🚫 Arquivos ou imagens não são aceitos. 📎"
                    )
                    continue  # Não retorna, aguarda outra mensagem

                # Se a mensagem não tiver anexos, retorna a mensagem
                return msg
                
        except asyncio.TimeoutError:
            # Finaliza o atendimento em caso de timeout
            self.aluno_cog.atendimento_ativo = False
            await interaction.followup.send(
                "Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`."
            )
            return None


    




    async def adicionar_duvida(self, interaction: discord.Interaction):
        await interaction.followup.send("Por favor, digite o título da sua dúvida.")

        titulo = await self.gerenciar_timeout(interaction, 3)
        
        if titulo is None:
            return
        
        titulo = titulo.content.strip()        

        await interaction.followup.send(
            f"✅ **Título registrado com sucesso:** **{titulo}**\n\n"
            "📨 Agora você pode digitar as mensagens da sua dúvida.\n"
            "✏️ Envie quantas mensagens forem necessárias para explicar sua dúvida.\n\n"
            "🔔 **Quando terminar, digite uma única mensagem com** `enviar` **para encaminhar ao coordenador.**\n\n"
            "⚠️ **Atenção:** Só aceitamos **mensagens de texto ou links**. Arquivos ou imagens não são permitidos."
        )


        mensagens=[]
        while True:    

            mensagem= await self.gerenciar_timeout(interaction, 30)
            
            if mensagem is None:
                deletar_duvida(interaction.user.name,titulo)
                return
            mensagem =mensagem.content.strip()
            

        
            if mensagem.lower() == "enviar":
                if len(mensagens)==0:
                    deletar_duvida(interaction.user.name,titulo)

                    await interaction.followup.send('Como você não adicionou nenhuma mensagem , sua dúvida não foi aceita!')
                break


            mensagens.append(mensagem)

        mensagem_unica="\n".join([f"- {msg}" for msg in mensagens])

        registrar_duvida_no_banco(interaction.user.name, titulo, mensagem_unica)
        
        await  self.load_submenu(interaction)        
        return 

    async def show_duvidas(self, interaction, duvidas):
        if not duvidas:
            await interaction.followup.send("Não há nenhuma dúvida.")
            await self.load_submenu(interaction)
            return
        

        titulos = list(duvidas.keys())
        enumeracao_titulos = "\n".join([f"{i + 1}. {titulo}" for i, titulo in enumerate(titulos)])  

        while True:
            await interaction.followup.send(
                f"Escolha o número de um título para visualizar as mensagens e respostas associadas:\n{enumeracao_titulos}\n99.Mostrar todas"
            )

            escolha = await self.gerenciar_timeout(interaction, 300)

            if escolha is None:
                return
            escolha = escolha.content.strip()

            if not escolha.isdigit():
                await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                continue

            escolha_index = int(escolha) - 1
            if escolha_index == 98:  # O índice 98 corresponde à escolha "99" (opção Mostrar todas)
                for titulo, dados in duvidas.items():
                    mensagens = dados.get("mensagem", {})
                    respostas = dados.get("resposta", {})
                    if dados.get("resposta"):
                        atualizar_visualizada(interaction.user.name,titulo)
                    
                    await interaction.followup.send(
                        f"**Título:** {titulo}\n"
                        f"**Mensagens:**\n{mensagens}\n\n"
                        f"**Respostas:**\n{respostas}\n\n"
                    )
                await self.load_submenu(interaction)
                return


            if escolha_index < 0 or escolha_index >= len(titulos):
                await interaction.followup.send("Escolha inválida. Por favor, escolha um número válido.")
                continue

           
            titulo_escolhido = titulos[escolha_index]
            dados = duvidas.get(titulo_escolhido, {})

            if dados.get("resposta"):
                atualizar_visualizada(interaction.user.name,titulo_escolhido)

            mensagens = dados.get("mensagem", {})
            respostas = dados.get("resposta", {})

            await interaction.followup.send(
                f"**Título:** {titulo_escolhido}\n"
                f"**Mensagens:**\n{mensagens}\n\n"
                f"**Respostas:**\n{respostas}\n\n"
            )
            await self.load_submenu(interaction)
            return

    
    async def show_editar_duvidas(self, interaction: discord.Interaction,user_duvidas):

        user_duvidas = user_duvidas

        if not user_duvidas:
            await interaction.followup.send("Você não tem dúvidas registradas para editar.")
            await  self.load_submenu(interaction)
            return
        
    
        await interaction.followup.send(
            "⚠️ **ATENÇÃO!**\n\n"
            "🛑 **Somente as dúvidas que NÃO foram respondidas podem ser editadas.**\n\n"
        )

        
        while True:
            titulos = list(user_duvidas.keys())
            enumeracao = "\n".join([f"{i + 1}. {titulo}" for i, titulo in enumerate(titulos)])
            await interaction.followup.send(
                f"Escolha o número de um título para editar uma mensagem associada:\n{enumeracao}"
            )            
            escolha = await self.gerenciar_timeout(interaction, 300)

            if escolha is None:
                return
            
            escolha=escolha.content.strip()
            
            if not escolha.isdigit():
                await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                
                continue
        
            escolha_index = int(escolha) - 1

            if escolha_index < 0 or escolha_index >= len(titulos):
                await interaction.followup.send("Escolha inválida. Tente novamente.", ephemeral=True)
                continue

            titulo_escolhido = titulos[escolha_index]
            mensagens = user_duvidas[titulo_escolhido]["mensagem"]
                               
            await interaction.followup.send(f"Mensagens registradas para o título **{titulo_escolhido}**:\n{mensagens}")

            await interaction.followup.send("Por favor, digite o novo título da sua dúvida.")

            titulo = await self.gerenciar_timeout(interaction, 300)
            
            if titulo is None:
                
                return
            novo_titulo = titulo.content.strip()

            await interaction.followup.send(f"Pode digitar a mensagem que irá substituíla , envie quantas quiser.Para finalizar envie uma única mensagem com 'enviar'")
            mensagens=[]
            while True:
                
                nova_msg =  await self.gerenciar_timeout(interaction, 300)
                
                if nova_msg is None:
                    return
                
                nova_msg=nova_msg.content.strip()

                if nova_msg.lower() == "enviar":
                    break

                mensagens.append(nova_msg)

            nova_msg_formatadas ="\n".join([f"- {msg}" for msg in mensagens]) 

            atualizar_mensagens(interaction.user.name,titulo_escolhido,nova_msg_formatadas,novo_titulo)

            await interaction.followup.send(f"**Dúvida atualizada com sucesso**\n"
                                            f"**Novo título:** {novo_titulo}\n" 
                                            f"**Novas mensagens:** \n{nova_msg_formatadas}"
                                            )
            await  self.load_submenu(interaction)
            return

    async def show_deletar_duvidas(self, interaction: discord.Interaction,user_duvidas):
        user_duvidas = user_duvidas

        if not user_duvidas:
            await interaction.followup.send("Você não tem dúvidas registradas para deletar.")
            await  self.load_submenu(interaction)
            return
        
        await interaction.followup.send(
            "⚠️ **ATENÇÃO!**\n\n"
            "🛑 **Somente as dúvidas que NÃO foram respondidas podem ser deletadas.**\n\n"
        )


        while True:

            titulos = list(user_duvidas.keys())
            enumeracao = "\n".join([f"{i + 1}. {titulo}" for i, titulo in enumerate(titulos)])
            await interaction.followup.send(
                f"Escolha o número de um título para deletar uma mensagem associada:\n{enumeracao}"
            )

            
            escolha = await self.gerenciar_timeout(interaction, 300)
            
            if escolha is None:
                return

            escolha=escolha.content.strip()

            if not escolha.isdigit():
                await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                continue
        
            escolha_index = int(escolha) - 1

            if escolha_index < 0 or escolha_index >= len(titulos):
                await interaction.followup.send("Escolha inválida. Tente novamente.", ephemeral=True)
                continue
        
            titulo_escolhido = titulos[escolha_index]

            deletar_duvida(interaction.user.name,titulo_escolhido)
            

            await interaction.followup.send(f"Dúvida {titulo_escolhido} excluída com sucesso!")
            await  self.load_submenu(interaction)
                    
            return


async def setup(bot):
    await bot.add_cog(Aluno(bot))
