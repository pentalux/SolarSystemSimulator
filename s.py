import pygame
import math
import numpy as np
import sys
from typing import List, Tuple, Optional

# Физические константы
G = 6.67430e-11  # Гравитационная постоянная
AU = 1.496e11    # Астрономическая единица (м)
SCALE = 50 / AU  # Масштаб для отображения
TIME_STEP = 3600 * 24  # Шаг времени (1 день)

class CelestialBody:
    def __init__(self, name: str, mass: float, position: Tuple[float, float], 
                 velocity: Tuple[float, float], color: Tuple[int, int, int], radius: int):
        self.name = name
        self.mass = mass
        self.position = np.array(position, dtype=float)
        self.velocity = np.array(velocity, dtype=float)
        self.color = color
        self.radius = radius
        self.trail = []
        self.max_trail_length = 800
        self.force_vector = np.array([0.0, 0.0])
        
    def update_trail(self):
        screen_pos = (self.position[0] * SCALE, self.position[1] * SCALE)
        self.trail.append(screen_pos)
        if len(self.trail) > self.max_trail_length:
            self.trail.pop(0)
    
    def calculate_force(self, other: 'CelestialBody') -> np.ndarray:
        r_vec = other.position - self.position
        r_mag = np.linalg.norm(r_vec)
        
        if r_mag == 0:
            return np.array([0.0, 0.0])
            
        # Более точная физика с меньшим softening
        softening = 1e4  # Уменьшил для более точных орбит
        r_mag_soft = np.sqrt(r_mag**2 + softening**2)
        force_mag = G * self.mass * other.mass / (r_mag_soft**2)
        force_vec = force_mag * r_vec / r_mag_soft
        
        return force_vec
    
    def update(self, bodies: List['CelestialBody'], dt: float):
        total_force = np.array([0.0, 0.0])
        
        for body in bodies:
            if body != self:
                total_force += self.calculate_force(body)
        
        self.force_vector = total_force
        acceleration = total_force / self.mass
        self.velocity += acceleration * dt
        self.position += self.velocity * dt
        self.update_trail()

class UIButton:
    def __init__(self, rect: pygame.Rect, text: str, color: Tuple[int, int, int], 
                 hover_color: Tuple[int, int, int], action: str):
        self.rect = rect
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.action = action
        self.is_hovered = False
        
    def draw(self, screen: pygame.Surface, font: pygame.font.Font):
        color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(screen, color, self.rect, border_radius=3)
        pygame.draw.rect(screen, (150, 150, 150), self.rect, 1, border_radius=3)
        
        text_surf = font.render(self.text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)
        
    def check_hover(self, pos: Tuple[int, int]):
        self.is_hovered = self.rect.collidepoint(pos)
        return self.is_hovered
        
    def is_clicked(self, pos: Tuple[int, int], clicked: bool) -> bool:
        return clicked and self.rect.collidepoint(pos)

class Slider:
    def __init__(self, rect: pygame.Rect, min_val: float, max_val: float, 
                 initial: float, label: str):
        self.rect = rect
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial
        self.label = label
        self.dragging = False
        self.knob_radius = 6
        
    def draw(self, screen: pygame.Surface, font: pygame.font.Font):
        # Линия слайдера
        line_rect = pygame.Rect(self.rect.x, self.rect.centery - 2, 
                               self.rect.width, 4)
        pygame.draw.rect(screen, (80, 80, 80), line_rect, border_radius=2)
        
        # Кнопка
        knob_x = self.rect.x + (self.value - self.min_val) / (self.max_val - self.min_val) * self.rect.width
        knob_pos = (int(knob_x), self.rect.centery)
        pygame.draw.circle(screen, (100, 150, 200), knob_pos, self.knob_radius)
        pygame.draw.circle(screen, (200, 200, 200), knob_pos, self.knob_radius, 1)
        
        # Текст
        label_surf = font.render(f"{self.label}: {self.value:.1f}", True, (255, 255, 255))
        screen.blit(label_surf, (self.rect.x, self.rect.y - 20))
        
    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN:
            knob_x = self.rect.x + (self.value - self.min_val) / (self.max_val - self.min_val) * self.rect.width
            knob_rect = pygame.Rect(knob_x - self.knob_radius, self.rect.centery - self.knob_radius,
                                   self.knob_radius * 2, self.knob_radius * 2)
            if knob_rect.collidepoint(event.pos):
                self.dragging = True
                return True
                
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
            
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            rel_x = max(0, min(event.pos[0] - self.rect.x, self.rect.width))
            self.value = self.min_val + (rel_x / self.rect.width) * (self.max_val - self.min_val)
            return True
            
        return False

class BodyEditor:
    def __init__(self):
        self.visible = False
        self.rect = pygame.Rect(400, 200, 400, 300)
        self.editing_body = None
        self.apply_button = UIButton(pygame.Rect(450, 450, 100, 30), "Apply", 
                                   (60, 120, 60), (80, 160, 80), "apply_edit")
        self.cancel_button = UIButton(pygame.Rect(570, 450, 100, 30), "Cancel", 
                                    (120, 60, 60), (160, 80, 80), "cancel_edit")
        
    def open(self, body: CelestialBody):
        self.visible = True
        self.editing_body = body
        
    def draw(self, screen: pygame.Surface, font: pygame.font.Font):
        if not self.visible:
            return
            
        # Фон редактора
        pygame.draw.rect(screen, (50, 50, 60), self.rect, border_radius=8)
        pygame.draw.rect(screen, (100, 100, 120), self.rect, 2, border_radius=8)
        
        # Заголовок
        title = font.render(f"Edit {self.editing_body.name}", True, (255, 255, 255))
        screen.blit(title, (self.rect.x + 20, self.rect.y + 20))
        
        # Информация о теле
        info_lines = [
            f"Mass: {self.editing_body.mass:.2e} kg",
            f"Position: ({self.editing_body.position[0]:.2e}, {self.editing_body.position[1]:.2e}) m",
            f"Velocity: ({self.editing_body.velocity[0]:.1f}, {self.editing_body.velocity[1]:.1f}) m/s",
            f"Speed: {np.linalg.norm(self.editing_body.velocity):.1f} m/s"
        ]
        
        y_offset = 60
        for line in info_lines:
            text = font.render(line, True, (200, 200, 255))
            screen.blit(text, (self.rect.x + 20, self.rect.y + y_offset))
            y_offset += 25
        
        # Кнопки
        self.apply_button.draw(screen, font)
        self.cancel_button.draw(screen, font)
        
    def handle_click(self, pos: Tuple[int, int]) -> str:
        if self.apply_button.is_clicked(pos, True):
            self.visible = False
            return "applied"
        elif self.cancel_button.is_clicked(pos, True):
            self.visible = False
            return "cancelled"
        return ""

class SolarSystemSim:
    def __init__(self):
        pygame.init()
        self.width, self.height = 1400, 900
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("My Solar System")
        self.clock = pygame.time.Clock()
        
        # Шрифты
        self.font_small = pygame.font.SysFont('Arial', 12)
        self.font_medium = pygame.font.SysFont('Arial', 14)
        self.font_large = pygame.font.SysFont('Arial', 16)
        
        # Состояние симуляции
        self.bodies = []
        self.paused = False
        self.show_trails = True
        self.show_vectors = False
        self.time_scale = 1.0
        
        # Камера - увеличиваем начальный масштаб для лучшего обзора
        self.camera_offset = pygame.Vector2(self.width // 2, self.height // 2)
        self.camera_scale = SCALE * 3.0  # Увеличиваем масштаб в 3 раза
        self.dragging = False
        self.drag_start = (0, 0)
        
        # Редактор тел
        self.body_editor = BodyEditor()
        
        # Создание UI элементов
        self.create_ui()
        
        # Предустановленные системы
        self.create_preset_systems()
        self.current_preset = "Solar System"
        self.create_solar_system()

    def create_ui(self):
        button_width, button_height = 120, 25
        margin = 8
        start_x = 10
        start_y = 10
        
        self.buttons = [
            UIButton(pygame.Rect(start_x, start_y, button_width, button_height), 
                    "Play/Pause", (70, 130, 70), (90, 170, 90), "toggle_pause"),
            UIButton(pygame.Rect(start_x, start_y + margin + button_height, button_width, button_height),
                    "Reset", (130, 70, 70), (170, 90, 90), "reset"),
            UIButton(pygame.Rect(start_x, start_y + 2*(margin + button_height), button_width, button_height),
                    "Clear All", (130, 100, 70), (170, 130, 90), "clear_all"),
            UIButton(pygame.Rect(start_x, start_y + 3*(margin + button_height), button_width, button_height),
                    "Show Trails", (80, 80, 130), (100, 100, 170), "toggle_trails"),
            UIButton(pygame.Rect(start_x, start_y + 4*(margin + button_height), button_width, button_height),
                    "Show Vectors", (80, 80, 130), (100, 100, 170), "toggle_vectors"),
            UIButton(pygame.Rect(start_x, start_y + 5*(margin + button_height), button_width, button_height),
                    "Add Body", (80, 130, 80), (100, 170, 100), "add_body"),
        ]
        
        # Слайдеры - увеличиваем максимальный зум
        slider_width, slider_height = 180, 15
        slider_start_x = 140
        slider_start_y = 15
        
        self.sliders = [
            Slider(pygame.Rect(slider_start_x, slider_start_y, slider_width, slider_height),
                  0.1, 10.0, 1.0, "Time Scale"),
            Slider(pygame.Rect(slider_start_x, slider_start_y + 35, slider_width, slider_height),
                  0.1, 6.0, 3.0, "Zoom"),  # Начальное значение 3.0
        ]
        
        # Кнопки предустановок
        preset_y = 70
        self.preset_buttons = []
        presets = ["Solar System", "Empty"]
        
        for i, preset in enumerate(presets):
            btn = UIButton(pygame.Rect(slider_start_x + i * 125, preset_y, 115, 25),
                          preset, (90, 90, 110), (110, 110, 150), f"preset_{preset}")
            self.preset_buttons.append(btn)

    def create_preset_systems(self):
        self.presets = {
            "Solar System": self.create_solar_system,
            "Empty": self.create_empty_system
        }

    def create_solar_system(self):
        # ОРИГИНАЛЬНАЯ ФИЗИКА - ничего не меняем!
        self.bodies = [
            # Солнце
            CelestialBody("Sun", 1.989e30, (0, 0), (0, 0), (255, 255, 0), 30),
            
            # Меркурий
            CelestialBody("Mercury", 3.301e23, (0.467*AU, 0), (0, 38860), (180, 180, 180), 4),
            
            # Венера
            CelestialBody("Venus", 4.867e24, (0, 0.723*AU), (-35020, 0), (255, 200, 100), 6),
            
            # Земля
            CelestialBody("Earth", 5.972e24, (-1.017*AU, 0), (0, -29290), (100, 100, 255), 7),
            
            # Марс
            CelestialBody("Mars", 6.417e23, (0, -1.666*AU), (21970, 0), (255, 100, 100), 5),
            
            # Юпитер
            CelestialBody("Jupiter", 1.898e27, (5.455*AU, 0), (0, 12440), (255, 165, 100), 15),
            
            # Сатурн
            CelestialBody("Saturn", 5.683e26, (0, -10.123*AU), (9680, 0), (255, 215, 150), 13),
            
            # Уран
            CelestialBody("Uranus", 8.681e25, (-20.11*AU, 0), (0, -6800), (170, 220, 255), 10),
            
            # Нептун
            CelestialBody("Neptune", 1.024e26, (0, 30.33*AU), (-5430, 0), (70, 130, 255), 10),
            
            # Плутон
            CelestialBody("Pluto", 1.309e22, (29.66*AU, 0), (0, 3710), (200, 180, 160), 2)
        ]
        self.current_preset = "Solar System"
    
    def create_empty_system(self):
        self.bodies = []
        self.current_preset = "Empty"
    
    def add_random_body(self):
        import random
        colors = [(255, 100, 100), (100, 255, 100), (100, 100, 255), 
                 (255, 255, 100), (255, 100, 255), (100, 255, 255)]
        
        mass = random.uniform(1e22, 1e25)
        x = random.uniform(-2*AU, 2*AU)
        y = random.uniform(-2*AU, 2*AU)
        vx = random.uniform(-10000, 10000)
        vy = random.uniform(-10000, 10000)
        color = random.choice(colors)
        radius = max(4, min(12, int(mass / 1e24)))
        
        new_body = CelestialBody(f"Body{len(self.bodies)+1}", mass, (x, y), (vx, vy), color, radius)
        self.bodies.append(new_body)
    
    def draw_arrow(self, start: Tuple[float, float], end: Tuple[float, float], color: Tuple[int, int, int], width: int = 2):
        """Рисует стрелку с наконечником"""
        pygame.draw.line(self.screen, color, start, end, width)
        
        # Вычисляем направление стрелки
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        angle = math.atan2(dy, dx)
        
        # Рисуем наконечник
        arrow_length = 10
        arrow_angle = math.pi / 6
        
        # Левая часть наконечника
        x1 = end[0] - arrow_length * math.cos(angle - arrow_angle)
        y1 = end[1] - arrow_length * math.sin(angle - arrow_angle)
        # Правая часть наконечника
        x2 = end[0] - arrow_length * math.cos(angle + arrow_angle)
        y2 = end[1] - arrow_length * math.sin(angle + arrow_angle)
        
        pygame.draw.line(self.screen, color, end, (x1, y1), width)
        pygame.draw.line(self.screen, color, end, (x2, y2), width)
    
    def draw_vectors(self):
        if not self.show_vectors:
            return
            
        for body in self.bodies:
            screen_x = body.position[0] * self.camera_scale + self.camera_offset.x
            screen_y = body.position[1] * self.camera_scale + self.camera_offset.y
            
            # Вектор скорости (зеленый) - адаптивный масштаб
            if np.linalg.norm(body.velocity) > 0:
                # Масштабируем скорость для визуализации (как в PhET)
                vel_magnitude = np.linalg.norm(body.velocity)
                # Логарифмическое масштабирование для лучшего отображения
                log_scale = math.log10(max(vel_magnitude, 100))  # Минимум 100 м/с
                vel_scale = min(1e3, 100 * log_scale)  # Ограничиваем максимальную длину
                
                vel_end_x = screen_x + body.velocity[0] * vel_scale
                vel_end_y = screen_y + body.velocity[1] * vel_scale
                
                # Ограничиваем максимальную длину вектора
                max_arrow_length = 200  # Максимум 200 пикселей
                current_length = math.dist((screen_x, screen_y), (vel_end_x, vel_end_y))
                if current_length > max_arrow_length:
                    scale_factor = max_arrow_length / current_length
                    vel_end_x = screen_x + (vel_end_x - screen_x) * scale_factor
                    vel_end_y = screen_y + (vel_end_y - screen_y) * scale_factor
                
                if current_length > 10:  # Рисуем только если достаточно длинный
                    self.draw_arrow((screen_x, screen_y), (vel_end_x, vel_end_y), (0, 255, 100), 2)
            
            # Вектор силы (красный) - адаптивный масштаб
            if np.linalg.norm(body.force_vector) > 0:
                # Масштабируем силу для визуализации
                force_magnitude = np.linalg.norm(body.force_vector)
                # Логарифмическое масштабирование
                log_scale = math.log10(max(force_magnitude, 1e10))  # Минимум 1e10 Н
                force_scale = min(1e12, 1e8 * log_scale)  # Ограничиваем длину
                
                force_end_x = screen_x + body.force_vector[0] * force_scale
                force_end_y = screen_y + body.force_vector[1] * force_scale
                
                # Ограничиваем максимальную длину вектора
                max_arrow_length = 150  # Максимум 150 пикселей
                current_length = math.dist((screen_x, screen_y), (force_end_x, force_end_y))
                if current_length > max_arrow_length:
                    scale_factor = max_arrow_length / current_length
                    force_end_x = screen_x + (force_end_x - screen_x) * scale_factor
                    force_end_y = screen_y + (force_end_y - screen_y) * scale_factor
                
                if current_length > 10:  # Рисуем только если достаточно длинный
                    self.draw_arrow((screen_x, screen_y), (force_end_x, force_end_y), (255, 80, 80), 2)
    
    def handle_events(self):
        mouse_pos = pygame.mouse.get_pos()
        mouse_clicked = False
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
                
            elif event.type == pygame.VIDEORESIZE:
                self.width, self.height = event.size
                self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
                # Обновляем смещение камеры при изменении размера окна
                self.camera_offset = pygame.Vector2(self.width // 2, self.height // 2)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_clicked = True
                if event.button == 1:  # Левая кнопка мыши
                    if self.body_editor.visible:
                        result = self.body_editor.handle_click(mouse_pos)
                        if result:
                            continue
                    
                    # Проверяем клик по телам для редактирования
                    for body in self.bodies:
                        screen_x = body.position[0] * self.camera_scale + self.camera_offset.x
                        screen_y = body.position[1] * self.camera_scale + self.camera_offset.y
                        distance = math.sqrt((mouse_pos[0] - screen_x)**2 + (mouse_pos[1] - screen_y)**2)
                        if distance <= body.radius:
                            self.body_editor.open(body)
                            break
                    else:
                        self.dragging = True
                        self.drag_start = mouse_pos
                    
                elif event.button == 4:  # Колесо мыши вверх - увеличение
                    self.camera_scale *= 1.2
                    self.sliders[1].value = min(3.0, self.sliders[1].value * 1.2)
                elif event.button == 5:  # Колесо мыши вниз - уменьшение
                    self.camera_scale /= 1.2
                    self.sliders[1].value = max(0.1, self.sliders[1].value / 1.2)
                    
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.dragging = False
                    
            elif event.type == pygame.MOUSEMOTION:
                if self.dragging:
                    dx = mouse_pos[0] - self.drag_start[0]
                    dy = mouse_pos[1] - self.drag_start[1]
                    self.camera_offset.x += dx
                    self.camera_offset.y += dy
                    self.drag_start = mouse_pos
            
            # Обработка слайдеров
            for slider in self.sliders:
                if slider.handle_event(event):
                    if slider.label == "Zoom":
                        self.camera_scale = SCALE * slider.value
        
        # Обновление состояния кнопок
        for button in self.buttons + self.preset_buttons:
            button.check_hover(mouse_pos)
            
            if button.is_clicked(mouse_pos, mouse_clicked):
                self.handle_button_action(button.action)
        
        # Обновление масштаба времени
        self.time_scale = self.sliders[0].value
        
        return True
    
    def handle_button_action(self, action: str):
        if action == "toggle_pause":
            self.paused = not self.paused
        elif action == "reset":
            self.presets[self.current_preset]()
        elif action == "clear_all":
            self.bodies = []
            self.current_preset = "Empty"
        elif action == "toggle_trails":
            self.show_trails = not self.show_trails
        elif action == "toggle_vectors":
            self.show_vectors = not self.show_vectors
        elif action == "add_body":
            self.add_random_body()
        elif action.startswith("preset_"):
            preset_name = action[7:]
            self.current_preset = preset_name
            self.presets[preset_name]()
    
    def update_simulation(self):
        if self.paused or not self.bodies:
            return
            
        dt = TIME_STEP * self.time_scale
        
        # Создаем копию тел для параллельного обновления
        bodies_copy = self.bodies.copy()
        
        for body in self.bodies:
            body.update(bodies_copy, dt)
    
    def draw_trails(self):
        if not self.show_trails:
            return
            
        for body in self.bodies:
            if len(body.trail) > 1:
                # Рисуем тропу с градиентом
                for i in range(1, len(body.trail)):
                    start_x = body.trail[i-1][0] * (self.camera_scale / SCALE) + self.camera_offset.x
                    start_y = body.trail[i-1][1] * (self.camera_scale / SCALE) + self.camera_offset.y
                    end_x = body.trail[i][0] * (self.camera_scale / SCALE) + self.camera_offset.x
                    end_y = body.trail[i][1] * (self.camera_scale / SCALE) + self.camera_offset.y
                    
                    alpha = i / len(body.trail)
                    color = tuple(int(c * alpha) for c in body.color)
                    pygame.draw.line(self.screen, color, (start_x, start_y), (end_x, end_y), 1)
    
    def draw_data_panel(self):
        panel_width = 280
        panel_height = 120
        panel_x = self.width - panel_width - 10
        panel_y = 10
        
        # Фон панели
        pygame.draw.rect(self.screen, (40, 40, 50), 
                        (panel_x, panel_y, panel_width, panel_height), border_radius=5)
        pygame.draw.rect(self.screen, (80, 80, 100), 
                        (panel_x, panel_y, panel_width, panel_height), 1, border_radius=5)
        
        # Данные
        y_offset = 15
        lines = [
            f"System: {self.current_preset}",
            f"Bodies: {len(self.bodies)}",
            f"Time Scale: {self.time_scale:.1f}x",
            f"Zoom: {self.camera_scale / SCALE:.1f}x",
            f"Status: {'Paused' if self.paused else 'Running'}",
        ]
        
        for line in lines:
            text = self.font_small.render(line, True, (255, 255, 255))
            self.screen.blit(text, (panel_x + 10, panel_y + y_offset))
            y_offset += 20
    
    def draw_ui(self):
        # Фон UI (полупрозрачный)
        ui_surface = pygame.Surface((self.width, 110), pygame.SRCALPHA)
        ui_surface.fill((30, 30, 40, 200))
        self.screen.blit(ui_surface, (0, 0))
        
        # Кнопки
        for button in self.buttons:
            button.draw(self.screen, self.font_medium)
        
        # Слайдеры
        for slider in self.sliders:
            slider.draw(self.screen, self.font_small)
        
        # Кнопки предустановок
        for button in self.preset_buttons:
            button.draw(self.screen, self.font_small)
    
    def draw(self):
        self.screen.fill((0, 0, 0))  # Черный фон
        
        # Рисуем тропы
        self.draw_trails()
        
        # Рисуем векторы с стрелками
        self.draw_vectors()
        
        # Рисуем небесные тела
        for body in self.bodies:
            screen_x = body.position[0] * self.camera_scale + self.camera_offset.x
            screen_y = body.position[1] * self.camera_scale + self.camera_offset.y
            
            # Рисуем тело
            pygame.draw.circle(self.screen, body.color, (int(screen_x), int(screen_y)), body.radius)
            
            # Обводка
            pygame.draw.circle(self.screen, (255, 255, 255), (int(screen_x), int(screen_y)), body.radius, 1)
            
            # Подпись
            name_text = self.font_small.render(body.name, True, (255, 255, 255))
            text_rect = name_text.get_rect(center=(int(screen_x), int(screen_y) + body.radius + 12))
            self.screen.blit(name_text, text_rect)
        
        # Рисуем UI
        self.draw_ui()
        self.draw_data_panel()
        
        # Рисуем редактор тел
        self.body_editor.draw(self.screen, self.font_medium)
        
        pygame.display.flip()
    
    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update_simulation()
            self.draw()
            self.clock.tick(60)

if __name__ == "__main__":
    sim = SolarSystemSim()
    sim.run()
    pygame.quit()
    sys.exit()