import discord
from discord.ext import commands
from discord import app_commands, Interaction
from discord.ui import View, button
from datetime import datetime
import asyncio


duvidas_por_usuario = {}

class Aluno(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.atendimento_ativo = False # Dicionário para controlar atendimentos ativos por usuário


    async def gerenciar_timeout(self, interaction, timeout=30):
        try:
            msg = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user, timeout=timeout)
            return msg
        except asyncio.TimeoutError:
            self.atendimento_ativo = False
            await interaction.followup.send(
                "Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`."
            )
            return None

    @app_commands.command(description='Inicia o atendimento e captura as mensagens com um título definido pelo usuário.')
    async def iniciar_atendimento(self, interaction: discord.Interaction):

        # Verifica se o usuário já tem um atendimento ativo
        if self.atendimento_ativo:
            await interaction.response.send_message(
                "Você já tem um atendimento em andamento. Por favor, finalize o atendimento atual antes de iniciar outro."
            )
            return
        
        await interaction.response.send_message('Bem vindo!')

        # Marca o atendimento como ativo
        self.atendimento_ativo = True

        menu_view = Menu_principal(self.bot, self)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message

        

        



class Menu_secundario(View):
    def __init__(self, bot, aluno_cog,timeout=30):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.aluno_cog = aluno_cog

    async def disable_buttons_and_update(self, interaction: discord.Interaction):
        """Desabilita todos os botões e atualiza a mensagem."""
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)



    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  
        if self.message:    
            await self.message.edit(content="Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`.",view=self)
            self.aluno_cog.atendimento_ativo=False
            return
        


    
    @button(label="Voltar ao menu principal", style=discord.ButtonStyle.primary)
    async def voltar_menu_principal(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)


        menu_view = Menu_principal(self.bot, self.aluno_cog)
        message = await interaction.followup.send(view=menu_view)
        menu_view.message = message

            

    
    @button(label="Finalizar atendimento", style=discord.ButtonStyle.danger)
    async def finalizar_atendimento(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)

        self.aluno_cog.atendimento_ativo=False

        await interaction.followup.send("Atendimento finalizado com sucesso! Você pode iniciar um novo atendimento com o comando `/iniciar_atendimento`.")
        

    

class Menu_principal(View):
    def __init__(self, bot, aluno_cog, timeout=30):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.aluno_cog = aluno_cog

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True 
        if self.message: 
            await self.message.edit(content="Tempo esgotado ! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`."
,view=self)
            self.aluno_cog.atendimento_ativo=False
            return
            


    async def disable_buttons_and_update(self, interaction: discord.Interaction):
        """Desabilita todos os botões e atualiza a mensagem."""
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        

    @button(label="Adicionar dúvida", style=discord.ButtonStyle.primary)
    async def adicionar_duvida(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)


        await interaction.followup.send("Por favor, digite o título da sua dúvida.")

        titulo = await self.aluno_cog.gerenciar_timeout(interaction, 10)
        
        if titulo is None:
            return
        titulo = titulo.content.strip()


        if interaction.user.name not in duvidas_por_usuario:
            duvidas_por_usuario[interaction.user.name] = {}
        duvidas_por_usuario[interaction.user.name][titulo] = {
            "mensagens": [],
            "respostas": [],
            "timestamp": datetime.now()  # Adiciona timestamp
        }

        await interaction.followup.send(
            f"Título registrado: **{titulo}**. Agora você pode digitar as mensagens da sua dúvida. "
            "Envie quantas mensagens quiser. Para enviar ao coordenador, envie uma mensagem com 'enviar'."
        )

        while True:
            

            mensagem= await self.aluno_cog.gerenciar_timeout(interaction, 10)
            
            if mensagem is None:
                del duvidas_por_usuario[interaction.user.name][titulo]
                return
            mensagem =mensagem.content.strip()
            

            if mensagem.lower() == "enviar":
                break

            duvidas_por_usuario[interaction.user.name][titulo]["mensagens"].append(mensagem)
        
        menu_view_secundario =  Menu_secundario(self.bot, self.aluno_cog)
        message = await interaction.followup.send(view=menu_view_secundario)
        menu_view_secundario.message = message
        return 



    @button(label="Visualizar dúvidas", style=discord.ButtonStyle.secondary)
    async def visualizar_duvidas(self, interaction: discord.Interaction, button):

        await self.disable_buttons_and_update(interaction)
        user_name = interaction.user.name
        user_duvidas = duvidas_por_usuario.get(user_name)

        if not user_duvidas:
            await interaction.followup.send('Não há nenhuma dúvida.')
            menu_view =  Menu_secundario(self.bot, self.aluno_cog)
            message = await interaction.followup.send(view=menu_view)
            menu_view.message = message
            return

        titulos = list(user_duvidas.keys())
        enumeracao = "\n".join([f"{i + 1}. {titulo}" for i, titulo in enumerate(titulos)])

        while True:
            await interaction.followup.send(
                f"Escolha o número de um título para visualizar as mensagens e respostas associadas:\n{enumeracao}"
            )
            
            escolha = await self.aluno_cog.gerenciar_timeout(interaction, 10)
            
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
            dados = user_duvidas.get(titulo_escolhido, {})
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

            menu_view =  Menu_secundario(self.bot, self.aluno_cog)
            message = await interaction.followup.send(view=menu_view)
            menu_view.message = message
            return

    @button(label="Editar Dúvida", style=discord.ButtonStyle.success)
    async def editar_dúvida(self, interaction: discord.Interaction, button):

        await self.disable_buttons_and_update(interaction)
        user_name = interaction.user.name
        user_duvidas = duvidas_por_usuario.get(user_name)

        if not user_duvidas:
            await interaction.followup.send("Você não tem dúvidas registradas para editar.")
            menu_view =  Menu_secundario(self.bot, self.aluno_cog)
            message = await interaction.followup.send(view=menu_view)
            menu_view.message = message
            return

        
        while True:
            titulos = list(user_duvidas.keys())
            enumeracao = "\n".join([f"{i + 1}. {titulo}" for i, titulo in enumerate(titulos)])
            await interaction.followup.send(
                f"Escolha o número de um título para editar uma mensagem associada:\n{enumeracao}"
            )

            
            escolha = await self.aluno_cog.gerenciar_timeout(interaction, 10)
            

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

            titulo = await self.aluno_cog.gerenciar_timeout(interaction, 10)
            
            if titulo is None:
                
                return
            titulo = titulo.content.strip()

            await interaction.followup.send(f"Pode digitar a mensagem que irá substitíla , envie quantas quiser.Para finalizar envie uma única mensagem com 'enviar'")
            
            titulo_escolhido= titulo
            mensagens = user_duvidas[titulo_escolhido]["mensagens"]
            mensagens.clear()

            while True:

                
                nova_msg =  await self.aluno_cog.gerenciar_timeout(interaction, 10)
                
                if nova_msg is None:
                    return
                
                nova_msg=nova_msg.content.strip()

                if nova_msg.lower() == "enviar":
                    break

                mensagens.append(nova_msg)

            nova_msg_formatadas ="\n".join(
                                    [f"- {msg}" for msg in mensagens]) if mensagens else "Nenhuma mensagem registrada."
                

            await interaction.followup.send(f"Mensagem atualizada com sucesso para: {nova_msg_formatadas}")
            
            menu_view =  Menu_secundario(self.bot, self.aluno_cog)
            message = await interaction.followup.send(view=menu_view)
            menu_view.message = message
            return


    @button(label="Deletar Dúvida", style=discord.ButtonStyle.danger)
    async def deletar_duvida(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
        user_name = interaction.user.name
        user_duvidas = duvidas_por_usuario.get(user_name)

        if not user_duvidas:
            await interaction.followup.send("Você não tem dúvidas registradas para deletar.")
            menu_view =  Menu_secundario(self.bot, self.aluno_cog)
            message = await interaction.followup.send(view=menu_view)
            menu_view.message = message
            return

        while True:

            titulos = list(user_duvidas.keys())
            enumeracao = "\n".join([f"{i + 1}. {titulo}" for i, titulo in enumerate(titulos)])
            await interaction.followup.send(
                f"Escolha o número de um título para deletar uma mensagem associada:\n{enumeracao}"
            )

            
            escolha = await self.aluno_cog.gerenciar_timeout(interaction, 10)
            
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
            
            menu_view =  Menu_secundario(self.bot, self.aluno_cog)
            message = await interaction.followup.send(view=menu_view)
            menu_view.message = message
            return
            

async def setup(bot):
    await bot.add_cog(Aluno(bot))



from discord.ext import commands
import discord
from discord import app_commands
import asyncio
from datetime import datetime
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import View, button


from Commands.aluno import duvidas_por_usuario  # Importa o dicionário compartilhado com as dúvidas

class Coordenador(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.atendimento_ativo = False  # Dicionário para controlar atendimentos ativos por usuário

    @app_commands.command(description="Visualizar títulos de dúvidas não respondidas e responder.")
    async def proximo_atendimento(self, interaction: discord.Interaction):


        if self.atendimento_ativo:
            await interaction.response.send_message(
                "Você já tem um atendimento em andamento. Por favor, finalize o atendimento atual antes de iniciar outro."
            )
            return

        # Marca o atendimento como ativo
        self.atendimento_ativo = True
        
        await interaction.response.send_message("Bem-vindo!")


        demanda_view = DemandaView(self.bot,self,self)
        message=await interaction.followup.send(view=demanda_view)
        demanda_view.message=message


           
                    
async def setup(bot):
    await bot.add_cog(Coordenador(bot))




class DemandaView(View):
    def __init__(self, bot,aluno_cog,usuario_atual,timeout=10):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.aluno_cog = aluno_cog
        self.usuario_atual=usuario_atual
    
    async def disable_buttons_and_update(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True 
        if self.message:  
            await self.message.edit(content="Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/proximo_atendimento`."
,view=self)
            self.aluno_cog.atendimento_ativo=False
            return

    

    @button(label="Atender próximo", style=discord.ButtonStyle.primary)
    async def atender_próximo(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)
        

        duvidas_agrupadas = {}
        for usuario_name, duvidas in duvidas_por_usuario.items():
            duvidas_sem_resposta = []
            for titulo, dados in duvidas.items():
                if not dados.get("respostas"):  
                    duvidas_sem_resposta.append({"titulo": titulo, "dados": dados})
            if duvidas_sem_resposta:
                duvidas_agrupadas[usuario_name] = duvidas_sem_resposta
        print(duvidas_agrupadas)
        
        

        if self.usuario_atual in duvidas_agrupadas:
            usuario_selecionado = self.usuario_atual
        else:
            
            usuarios_com_duvidas_ordenadas = [
                (usuario_name, min(dados["dados"].get("timestamp", datetime.max) for dados in duvidas))
                for usuario_name, duvidas in duvidas_agrupadas.items()
            ]

            usuarios_com_duvidas_ordenadas.sort(key=lambda x: x[1])

            usuario_selecionado = usuarios_com_duvidas_ordenadas[0][0]
            self.usuario_atual = usuario_selecionado
                
            if not usuarios_com_duvidas_ordenadas:
                await interaction.followup.send("Não há dúvidas pendentes no momento.")
                demanda_view = DemandaView(self.bot, self.aluno_cog,self.usuario_atual)
                await interaction.followup.send(view=demanda_view)
                return

            
        duvidas_usuario = duvidas_agrupadas[usuario_selecionado]

        while True:
            lista_titulos = "\n".join([
            f"{i + 1}. {item['titulo']}"
            for i, item in enumerate(duvidas_usuario)
                                                        ])
            await interaction.followup.send(
                f"Dúvidas de {usuario_selecionado}:\n{lista_titulos}\n"
                "Escolha um título pela posição na lista para visualizar as mensagens."
            )

            try:

                escolha_titulo = await self.bot.wait_for('message',check=lambda m: m.author == interaction.user,timeout=30)

            except asyncio.TimeoutError:

                self.aluno_cog.atendimento_ativo=False
                await interaction.followup.send(
                    "Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/proximo_atendimento`."
                )
                return                    
        
            if not escolha_titulo.content.isdigit():  # Verifica se não é um número
                await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                continue

        
            escolha_titulo_index = int(escolha_titulo.content) - 1

            if escolha_titulo_index < 0 or escolha_titulo_index >= len(duvidas_usuario):
                await interaction.followup.send("Escolha inválida. Por favor, tente novamente.")
                continue

            titulo_selecionado = duvidas_usuario[escolha_titulo_index]
            titulo = titulo_selecionado["titulo"]
            dados = titulo_selecionado["dados"]
            
            mensagens = dados.get("mensagens", [])
            
            mensagens_formatadas = "\n".join([f"- {msg}" for msg in mensagens]) if mensagens else "Nenhuma mensagem registrada."

            await interaction.followup.send(
                f"**Título : {titulo}**\n\n"
                f"**Mensagens:**\n{mensagens_formatadas}\n\n"
                "Agora você pode responder a essa dúvida. Envie suas respostas.\n"
                "Envie uma mensagem com somente 'enviar' para encerrar."
            )

            respostas = []
            while True:
                try:
                    resposta_msg = await self.bot.wait_for('message',check=lambda m: m.author == interaction.user,timeout=30)

                    resposta = resposta_msg.content
                except asyncio.TimeoutError:
                    self.aluno_cog.atendimento_ativo=False
                    await interaction.followup.send(
                        "Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/proximo_atendimento`."
                    )
                    return

                if resposta.lower() == 'enviar':
                    break
                
                respostas.append(resposta)

            # Adicionar respostas ao título
            dados["respostas"].extend(respostas)
            await interaction.followup.send(
                f"Respostas adicionadas ao título **{titulo}**:\n"
                f"{chr(10).join([f'- {r}' for r in respostas])}\n"
                f"O título foi atualizado com as novas respostas.\n\n"
            )
            demanda_view = DemandaView(self.bot, self.aluno_cog,self.usuario_atual)
            await interaction.followup.send(view=demanda_view)
            return
            
        


    @button(label="Visualizar respostas", style=discord.ButtonStyle.secondary)
    async def visualizar_respostas(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)

        # Filtra as dúvidas que possuem respostas
        duvidas_com_respostas = {}
        for usuario_name, duvidas in duvidas_por_usuario.items():
            duvidas_com_resposta = []
            for titulo, dados in duvidas.items():
                if dados.get("respostas"):  # Verifica se há respostas
                    duvidas_com_resposta.append({"titulo": titulo, "dados": dados})
            if duvidas_com_resposta:
                duvidas_com_resposta.sort(key=lambda d: d["dados"]["timestamp"])
                duvidas_com_respostas[usuario_name] = duvidas_com_resposta
        print(duvidas_com_respostas)


        if not duvidas_com_respostas:
            await interaction.followup.send("Não há respostas registradas para exibir.")
            demanda_view = DemandaView(self.bot, self.aluno_cog,self.usuario_atual)
            await interaction.followup.send(view=demanda_view)
            return
            
            

        # Lista usuários com dúvidas respondidas
        usuarios_com_respostas = sorted(
            duvidas_com_respostas.keys(),
            key=lambda usuario: duvidas_com_respostas[usuario][0]["dados"]["timestamp"])
        
    
        while True:
            lista_usuarios = "\n".join([f"{i + 1}. {user}" for i, user in enumerate(usuarios_com_respostas)])
            await interaction.followup.send(
                f"Escolha um usuário para visualizar as respostas associadas às dúvidas:\n{lista_usuarios}"
            )
            try:

                escolha_usuario = await self.bot.wait_for('message',check=lambda m: m.author == interaction.user,timeout=30)
            except asyncio.TimeoutError:
                self.atendimento_ativo = False
                await interaction.followup.send(
                    "Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`."
                )
                return
            
            if not escolha_usuario.content.isdigit():
                await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                continue
            
        
            escolha_usuario_index = int(escolha_usuario.content) - 1

            if escolha_usuario_index < 0 or escolha_usuario_index >= len(usuarios_com_respostas):
                await interaction.followup.send("Escolha inválida. Por favor, tente novamente.")
                continue

            usuario_selecionado = usuarios_com_respostas[escolha_usuario_index]
            duvidas_usuario = duvidas_com_respostas[usuario_selecionado]

                    

            while True:
                lista_titulos = "\n".join([f"{i + 1}. {item['titulo']}" for i, item in enumerate(duvidas_usuario)])

            
                await interaction.followup.send(
                    f"Escolha um título para visualizar as respostas:\n{lista_titulos}"
                )
                try:

                    escolha_titulo = await self.bot.wait_for('message',check=lambda m: m.author == interaction.user)
                except asyncio.TimeoutError:
                    self.atendimento_ativo = False
                    await interaction.followup.send(
                        "Tempo esgotado! O atendimento foi encerrado. Você pode iniciar novamente usando `/iniciar_atendimento`."
                    )
                    return
                
                if not escolha_titulo.content.isdigit():
                    await interaction.followup.send("Escolha inválida. Por favor, envie um número.")
                    continue
            

                escolha_titulo_index = int(escolha_titulo.content) - 1

                if escolha_titulo_index < 0 or escolha_titulo_index >= len(duvidas_usuario):
                    await interaction.followup.send("Escolha inválida. Por favor, tente novamente.")
                    continue
                
                titulo_selecionado = duvidas_usuario[escolha_titulo_index]
                titulo = titulo_selecionado["titulo"]
                dados = titulo_selecionado["dados"]
                mensagens= dados.get("mensagens", [])
                respostas = dados.get("respostas", [])
                
                mensagens_formatadas = "\n".join(
                [f"- {msg}" for msg in mensagens]) if mensagens else "Nenhuma mensagem registrada."
                respostas_formatadas = "\n".join(
                [f"- {resp}" for resp in respostas]) if respostas else "Nenhuma resposta registrada."

                            
                await interaction.followup.send(
                    f"**Título:** {titulo}\n"
                    f"**Mensagens:**\n{mensagens_formatadas}\n\n"
                    f"**Respostas:**\n{respostas_formatadas}\n\n"
                )
                demanda_view = DemandaView(self.bot, self.aluno_cog,self.usuario_atual)
                await interaction.followup.send(view=demanda_view)

                return
                

    
                                        
    @button(label="Finalizar demanda", style=discord.ButtonStyle.danger)
    async def finalizar_demanda(self, interaction: discord.Interaction, button):
        await self.disable_buttons_and_update(interaction)


        self.atendimento_ativo = False

        await interaction.followup.send(
            "Demanda finalizada com sucesso."
        )
        

