import discord
from discord.ext import commands
from discord import app_commands, Interaction
from discord.ui import View, button
from datetime import datetime,timedelta
import asyncio


duvidas_por_usuario = {}

class Aluno(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.atendimento_ativo = False # Dicionário para controlar atendimentos ativos por usuário

    def obter_duvidas_respondidas(self, user_name):
        user_duvidas = duvidas_por_usuario.get(user_name, {})
        duvidas_respondidas = {
            titulo: dados
            for titulo, dados in user_duvidas.items()
            if dados.get("respostas") 
        }
        return duvidas_respondidas
    
    def obter_duvidas_nao_respondidas(self, user_name):
        user_duvidas = duvidas_por_usuario.get(user_name, {})
        duvidas_nao_respondidas = {
            titulo: dados
            for titulo, dados in user_duvidas.items()
            if not dados.get("respostas")
        }
        return duvidas_nao_respondidas

    

    # FUNÇÃO QUE VERIFICA O TEMPO DE RESPOSTA DO USUÁRIO AO BOT
    async def gerenciar_timeout(self, interaction, timeout):
        
        try:
            # Aguarda uma mensagem do usuário
            msg = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user, timeout=timeout)
            return msg  
        except asyncio.TimeoutError:
            # Finaliza o atendimento em caso de timeout
            self.atendimento_ativo = False
            await interaction.followup.send(
                "Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`."
            )
            return None
        
    def obter_duvidas_com_resposta_nao_visualizada(self, user_name):
        user_duvidas = duvidas_por_usuario.get(user_name, {})
        nao_visualizadas = {
            titulo: dados
            for titulo, dados in user_duvidas.items()
            if dados.get("respostas") and dados.get("visualizada") is False
        }
        return nao_visualizadas


        
    # FUNÇÃO PARA QUE O USUÁRIO CONSIGA INICIAR O ATENDIMENTO
    @app_commands.command(description='Inicia o atendimento e captura as mensagens com um título definido pelo usuário.')
    async def iniciar_atendimento(self, interaction: discord.Interaction):

        # Verifica se o usuário já tem um atendimento ativo
        if self.atendimento_ativo:
            await interaction.response.send_message(
                "Você já tem um atendimento em andamento. Por favor, finalize o atendimento atual antes de iniciar outro."
            )
            return
        user_name = interaction.user.name
        duvidas_nao_visualizadas = self.obter_duvidas_com_resposta_nao_visualizada(user_name)
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


        
        

        # Marca o atendimento como ativo
        self.atendimento_ativo = True

        # ENVIA A CLASSE DE VIEW COM BOTÕES PARA O MENU PRINCIPAL 
        menu_view = Menu(self.bot, self)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message 
    


class Menu(View):
    def __init__(self, bot, aluno_cog, timeout=5):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.aluno_cog = aluno_cog

    # FUNÇÃO QUE VERIFICA A INTERAÇÃO DO USUÁRIO COM A VIEW DO MENU
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True 
        if self.message: 
            await self.message.edit(content="Tempo esgotado ! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`.",view=self)
            self.aluno_cog.atendimento_ativo=False
            return
        
     #FUNÇÃO QUE CARREGA O SUBMENU
    async def load_duvidas(self,interaction):
        menu_view =  Duvidas(self.bot, self.aluno_cog)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message
        
    #FUNÇÃO QUE CARREGA O SUBMENU
    async def load_submenu(self,interaction):
        menu_view =  Submenu(self.bot, self.aluno_cog)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message

    #FUNÇÃO QUE DESABILITA AS MENSAGENS QUANDO O USÁRIO INTERAGIR COM ALGUM BOTÃO DA VIEW
    async def disable_buttons_and_update(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.message=None
        
    #BOTÃO DE ADICIONAR DÚVIDA
    @button(label="Adicionar dúvida", style=discord.ButtonStyle.primary)
    async def adicionar_duvida(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)

        await interaction.followup.send("Por favor, digite o título da sua dúvida.")

        titulo = await self.aluno_cog.gerenciar_timeout(interaction, 300)
        
        if titulo is None:
            return
        
        titulo = titulo.content.strip()

        if interaction.user.name not in duvidas_por_usuario:
            duvidas_por_usuario[interaction.user.name] = {}
        duvidas_por_usuario[interaction.user.name][titulo] = {
            "mensagens": [],
            "respostas": [],
            "visualizada":False,
            "timestamp": datetime.now()  # Adiciona timestamp
        }

        await interaction.followup.send(
            f"Título registrado: **{titulo}**. Agora você pode digitar as mensagens da sua dúvida. "
            "Envie quantas mensagens quiser. Para enviar ao coordenador, envie uma mensagem com 'enviar'."
        )

        while True:    

            mensagem= await self.aluno_cog.gerenciar_timeout(interaction, 300)
            
            if mensagem is None:
                del duvidas_por_usuario[interaction.user.name][titulo]
                return
            mensagem =mensagem.content.strip()
            

            if mensagem.lower() == "enviar":
                break

            duvidas_por_usuario[interaction.user.name][titulo]["mensagens"].append(mensagem)
        
        await  self.load_submenu(interaction)        
        return 

    #BOTÃO DE VISUALIZAR DÚVIDAS
    @button(label="Visualizar dúvidas", style=discord.ButtonStyle.secondary)
    async def visualizar_duvidas(self, interaction: discord.Interaction, button):

        await self.disable_buttons_and_update(interaction)
        await self.load_duvidas(interaction)
   
        

    #BOTÃO DE EDITAR DÚVIDA
    @button(label="Editar Dúvida", style=discord.ButtonStyle.success)
    async def editar_dúvida(self, interaction: discord.Interaction, button):

        await self.disable_buttons_and_update(interaction)
        user_name = interaction.user.name
        user_duvidas = duvidas_por_usuario.get(user_name)

        if not user_duvidas:
            await interaction.followup.send("Você não tem dúvidas registradas para editar.")
            await  self.load_submenu(interaction)
            return

        
        while True:
            titulos = list(user_duvidas.keys())
            enumeracao = "\n".join([f"{i + 1}. {titulo}" for i, titulo in enumerate(titulos)])
            await interaction.followup.send(
                f"Escolha o número de um título para editar uma mensagem associada:\n{enumeracao}"
            )            
            escolha = await self.aluno_cog.gerenciar_timeout(interaction, 300)

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
            mensagens = user_duvidas[titulo_escolhido]["mensagens"]
            mensagens_formatadas = "\n".join(
                                    [f"- {msg}" for msg in mensagens]) if mensagens else "Nenhuma mensagem registrada."
                                                    
            await interaction.followup.send(f"Mensagens registradas para o título **{titulo_escolhido}**:\n{mensagens_formatadas}")

            await interaction.followup.send("Por favor, digite o novo título da sua dúvida.")

            titulo = await self.aluno_cog.gerenciar_timeout(interaction, 300)
            
            if titulo is None:
                
                return
            novo_titulo = titulo.content.strip()

            await interaction.followup.send(f"Pode digitar a mensagem que irá substituíla , envie quantas quiser.Para finalizar envie uma única mensagem com 'enviar'")

            user_duvidas[novo_titulo]= user_duvidas.pop(titulo_escolhido)
            mensagens = user_duvidas[novo_titulo]["mensagens"]
            mensagens.clear()

            while True:

                
                nova_msg =  await self.aluno_cog.gerenciar_timeout(interaction, 300)
                
                if nova_msg is None:
                    return
                
                nova_msg=nova_msg.content.strip()

                if nova_msg.lower() == "enviar":
                    break

                mensagens.append(nova_msg)

            nova_msg_formatadas ="\n".join([f"- {msg}" for msg in mensagens]) if mensagens else "Nenhuma mensagem registrada."

            await interaction.followup.send(f"**Dúvida atualizada com sucesso**\n"
                                            f"**Novo título:** {novo_titulo}\n" 
                                            f"**Novas mensagens:** \n{nova_msg_formatadas}"
                                            )
            await  self.load_submenu(interaction)
            
            
            return

    #BOTÃO DE DELETAR DÚVIDA
    @button(label="Deletar Dúvida", style=discord.ButtonStyle.danger)
    async def deletar_duvida(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
        user_name = interaction.user.name
        user_duvidas = duvidas_por_usuario.get(user_name)

        if not user_duvidas:
            await interaction.followup.send("Você não tem dúvidas registradas para deletar.")
            await  self.load_submenu(interaction)
            return

        while True:

            titulos = list(user_duvidas.keys())
            enumeracao = "\n".join([f"{i + 1}. {titulo}" for i, titulo in enumerate(titulos)])
            await interaction.followup.send(
                f"Escolha o número de um título para deletar uma mensagem associada:\n{enumeracao}"
            )

            
            escolha = await self.aluno_cog.gerenciar_timeout(interaction, 300)
            
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

            del user_duvidas[titulo_escolhido]
            

            await interaction.followup.send(f"Dúvida {titulo_escolhido} excluída com sucesso!")
            await  self.load_submenu(interaction)
            
            
            return
        
class Submenu(View):
    def __init__(self, bot, aluno_cog,timeout=5):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.aluno_cog = aluno_cog

    #FUÇÃO QUE DESABILITA AS MENSAGENS QUANDO O USÁRIO INTERAGIR COM ALGUM BOTÃO DA VIEW
    async def disable_buttons_and_update(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.message=None


    # FUNÇÃO QUE VERIFICA A INTERAÇÃO DO USUÁRIO COM A VIEW DO MENU
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  
        if self.message:    
            await self.message.edit(content="Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`.",view=self)
            self.aluno_cog.atendimento_ativo=False
            return
        
    # BOTÃO DE VOLTAR AO MENU
    @button(label="Voltar ao menu principal", style=discord.ButtonStyle.primary)
    async def voltar_menu(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)

        menu_view = Menu(self.bot, self.aluno_cog)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message

    # BOTÃO DE FINALIZAR ATENDIMENTO
    @button(label="Finalizar atendimento", style=discord.ButtonStyle.danger)
    async def finalizar_atendimento(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)

        self.aluno_cog.atendimento_ativo=False

        await interaction.followup.send("Atendimento finalizado com sucesso! Você pode iniciar um novo atendimento com o comando `/iniciar_atendimento`.")
            


class Duvidas(View):
    def __init__(self, bot, aluno_cog,timeout=5):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.aluno_cog = aluno_cog

   

    #FUÇÃO QUE DESABILITA AS MENSAGENS QUANDO O USÁRIO INTERAGIR COM ALGUM BOTÃO DA VIEW
    async def disable_buttons_and_update(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.message=None

    #FUNÇÃO QUE CARREGA O SUBMENU
    async def load_filtro_duvidas(self,interaction,duvidas):
        menu_view = Filtro_duvidas(self.bot, self.aluno_cog,duvidas)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message



    # FUNÇÃO QUE VERIFICA A INTERAÇÃO DO USUÁRIO COM A VIEW DO MENU
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  
        if self.message:    
            await self.message.edit(content="Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`.",view=self)
            self.aluno_cog.atendimento_ativo=False
            return
        
    @button(label="Respondidas", style=discord.ButtonStyle.primary)
    async def duvidas_respondidas(self, interaction: discord.Interaction,button):
        await self.disable_buttons_and_update(interaction)
        user_name = interaction.user.name
        duvidas = self.aluno_cog.obter_duvidas_respondidas(user_name)
        await self.load_filtro_duvidas(interaction,duvidas)
        
    @button(label="Não Respondidas", style=discord.ButtonStyle.secondary)
    async def duvidas_nao_respondidas(self, interaction: discord.Interaction,button):
        await self.disable_buttons_and_update(interaction) 
        user_name = interaction.user.name
        duvidas = self.aluno_cog.obter_duvidas_nao_respondidas(user_name)
        await self.load_filtro_duvidas(interaction,duvidas)


class Filtro_duvidas(View):
    def __init__(self, bot, aluno_cog, duvidas,timeout=5):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.aluno_cog = aluno_cog
        self.duvidas=duvidas

    async def disable_buttons_and_update(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.message=None

     #FUNÇÃO QUE CARREGA O SUBMENU
    async def load_submenu(self,interaction):
        menu_view =  Submenu(self.bot, self.aluno_cog)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message


    # FUNÇÃO QUE VERIFICA A INTERAÇÃO DO USUÁRIO COM A VIEW DO MENU
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True 
        if self.message: 
            await self.message.edit(content="Tempo esgotado ! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`.",view=self)
            self.aluno_cog.atendimento_ativo=False
            return
        
    
    # BOTÃO DE FINALIZAR ATENDIMENTO
    @button(label="Hoje", style=discord.ButtonStyle.primary)
    async def hoje(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)


        agora = datetime.now()
        inicio_periodo = agora.replace(hour=0, minute=0, second=0, microsecond=0)  # Início de hoje

        duvidas = {
            titulo: dados
            for titulo, dados in self.duvidas.items()
            if dados["timestamp"] >= inicio_periodo  # Verifica se o timestamp é de hoje
         }


        if not duvidas:
            await interaction.followup.send('Não há nenhuma dúvida de hoje')
            await  self.load_submenu(interaction)
            return

        titulos = list(duvidas.keys())
        enumeracao = "\n".join([f"{i + 1}. {titulo}" for i, titulo in enumerate(titulos)])

        while True:
            await interaction.followup.send(
                f"Escolha o número de um título para visualizar as mensagens e respostas associadas:\n{enumeracao}"
            )
            
            escolha = await self.aluno_cog.gerenciar_timeout(interaction, 300)
            
            if escolha is None:
                return
            escolha=escolha.content.strip()
            

            if not escolha.isdigit():
                await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                continue
        
            escolha_index = int(escolha) - 1

            if escolha_index < 0 or escolha_index >= len(titulos):
                await interaction.followup.send("Escolha inválida. Por favor, escolha um número válido.")
                continue
            
            titulo_escolhido = titulos[escolha_index]
            dados = duvidas.get(titulo_escolhido, {})
            if dados.get("respostas"):
                dados["visualizada"] = True

            mensagens = dados.get("mensagens", [])
            respostas = dados.get("respostas", [])
           

            mensagens_formatadas = "\n".join(
                [f"- {msg}" for msg in mensagens]) if mensagens else "Nenhuma mensagem registrada."
            respostas_formatadas = "\n".join(
                [f"- {resp}" for resp in respostas]) if respostas else "Nenhuma resposta registrada."

            await interaction.followup.send(
                f"**Título:** {titulo_escolhido}\n"
                f"**Mensagens:**\n{mensagens_formatadas}\n\n"
                f"**Respostas:**\n{respostas_formatadas}\n\n"
            )
            await  self.load_submenu(interaction)
            return

     # BOTÃO DE FINALIZAR ATENDIMENTO
    @button(label="7 dias", style=discord.ButtonStyle.secondary)
    async def dias_7(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
          


        agora = datetime.now()
        inicio_periodo = agora - timedelta(days=7)  # 7 dias atrás

        duvidas = {
            titulo: dados
            for titulo, dados in self.duvidas.items()
            if dados["timestamp"] >= inicio_periodo  # Verifica se o timestamp é de hoje
         }


        if not duvidas:
            await interaction.followup.send('Não há nenhuma dúvida nos últimos 7 dias.')
            await  self.load_submenu(interaction)
            return

        titulos = list(duvidas.keys())
        enumeracao = "\n".join([f"{i + 1}. {titulo}" for i, titulo in enumerate(titulos)])

        while True:
            await interaction.followup.send(
                f"Escolha o número de um título para visualizar as mensagens e respostas associadas:\n{enumeracao}"
            )
            
            escolha = await self.aluno_cog.gerenciar_timeout(interaction, 300)
            
            if escolha is None:
                return
            escolha=escolha.content.strip()
            

            if not escolha.isdigit():
                await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                continue
        
            escolha_index = int(escolha) - 1

            if escolha_index < 0 or escolha_index >= len(titulos):
                await interaction.followup.send("Escolha inválida. Por favor, escolha um número válido.")
                continue
            
            titulo_escolhido = titulos[escolha_index]
            dados = duvidas.get(titulo_escolhido, {})
            if dados.get("respostas"):
                dados["visualizada"] = True

            mensagens = dados.get("mensagens", [])
            respostas = dados.get("respostas", [])
           

            mensagens_formatadas = "\n".join(
                [f"- {msg}" for msg in mensagens]) if mensagens else "Nenhuma mensagem registrada."
            respostas_formatadas = "\n".join(
                [f"- {resp}" for resp in respostas]) if respostas else "Nenhuma resposta registrada."

            await interaction.followup.send(
                f"**Título:** {titulo_escolhido}\n"
                f"**Mensagens:**\n{mensagens_formatadas}\n\n"
                f"**Respostas:**\n{respostas_formatadas}\n\n"
            )
            await  self.load_submenu(interaction)
            return


     # BOTÃO DE FINALIZAR ATENDIMENTO
    @button(label="30 dias", style=discord.ButtonStyle.success)
    async def dias_30(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
          


        agora = datetime.now()
        inicio_periodo = agora - timedelta(days=30)  # 7 dias atrás

        duvidas = {
            titulo: dados
            for titulo, dados in self.duvidas.items()
            if dados["timestamp"] >= inicio_periodo  # Verifica se o timestamp é de hoje
         }


        if not duvidas:
            await interaction.followup.send('Não há nenhuma dúvida nos últimos 7 dias.')
            await  self.load_submenu(interaction)
            return

        titulos = list(duvidas.keys())
        enumeracao = "\n".join([f"{i + 1}. {titulo}" for i, titulo in enumerate(titulos)])

        while True:
            await interaction.followup.send(
                f"Escolha o número de um título para visualizar as mensagens e respostas associadas:\n{enumeracao}"
            )
            
            escolha = await self.aluno_cog.gerenciar_timeout(interaction, 300)
            
            if escolha is None:
                return
            escolha=escolha.content.strip()
            

            if not escolha.isdigit():
                await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                continue
        
            escolha_index = int(escolha) - 1

            if escolha_index < 0 or escolha_index >= len(titulos):
                await interaction.followup.send("Escolha inválida. Por favor, escolha um número válido.")
                continue
            
            titulo_escolhido = titulos[escolha_index]
            dados = duvidas.get(titulo_escolhido, {})
            if dados.get("respostas"):
                dados["visualizada"] = True

            mensagens = dados.get("mensagens", [])
            respostas = dados.get("respostas", [])
           

            mensagens_formatadas = "\n".join(
                [f"- {msg}" for msg in mensagens]) if mensagens else "Nenhuma mensagem registrada."
            respostas_formatadas = "\n".join(
                [f"- {resp}" for resp in respostas]) if respostas else "Nenhuma resposta registrada."

            await interaction.followup.send(
                f"**Título:** {titulo_escolhido}\n"
                f"**Mensagens:**\n{mensagens_formatadas}\n\n"
                f"**Respostas:**\n{respostas_formatadas}\n\n"
            )
            await  self.load_submenu(interaction)
            return
        

     # BOTÃO DE FINALIZAR ATENDIMENTO
    @button(label="Todas", style=discord.ButtonStyle.danger)
    async def Todas(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
          

        duvidas = {
            titulo: dados
            for titulo, dados in self.duvidas.items()
         }


        if not duvidas:
            await interaction.followup.send('Não há nenhuma dúvida.')
            await  self.load_submenu(interaction)
            return

        titulos = list(duvidas.keys())
        enumeracao = "\n".join([f"{i + 1}. {titulo}" for i, titulo in enumerate(titulos)])

        while True:
            await interaction.followup.send(
                f"Escolha o número de um título para visualizar as mensagens e respostas associadas:\n{enumeracao}"
            )
            
            escolha = await self.aluno_cog.gerenciar_timeout(interaction, 300)
            
            if escolha is None:
                return
            escolha=escolha.content.strip()
            

            if not escolha.isdigit():
                await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                continue
        
            escolha_index = int(escolha) - 1

            if escolha_index < 0 or escolha_index >= len(titulos):
                await interaction.followup.send("Escolha inválida. Por favor, escolha um número válido.")
                continue
            
            titulo_escolhido = titulos[escolha_index]
            dados = duvidas.get(titulo_escolhido, {})
            if dados.get("respostas"):
                dados["visualizada"] = True

            mensagens = dados.get("mensagens", [])
            respostas = dados.get("respostas", [])
           

            mensagens_formatadas = "\n".join(
                [f"- {msg}" for msg in mensagens]) if mensagens else "Nenhuma mensagem registrada."
            respostas_formatadas = "\n".join(
                [f"- {resp}" for resp in respostas]) if respostas else "Nenhuma resposta registrada."

            await interaction.followup.send(
                f"**Título:** {titulo_escolhido}\n"
                f"**Mensagens:**\n{mensagens_formatadas}\n\n"
                f"**Respostas:**\n{respostas_formatadas}\n\n"
            )
            await  self.load_submenu(interaction)
            return


    
        
   
async def setup(bot):
    await bot.add_cog(Aluno(bot))
