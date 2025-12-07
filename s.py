import pygame
import math
import numpy as np
import sys
import random
from typing import List, Tuple
import pygame_gui
import os

G = 6.67430e-11
AU = 1.496e11
BASE_PIXEL_SCALE = 250 / AU 
TIME_STEP = 3600 * 24 #1д

VELOCITY_VISUAL_SCALE = 0.002

class Star:
    def __init__(self, w, h):
        self.x = random.randint(-w * 2, w * 3)
        self.y = random.randint(-h * 2, h * 3)
        self.z = random.uniform(0.5, 3.0) 
        self.brightness = random.randint(50, 200)
        self.size = random.randint(1, 2)

class CelestialBody:
    def __init__(self, name: str, mass: float, position: Tuple[float, float], 
                 velocity: Tuple[float, float], color: Tuple[int, int, int], base_radius: int):
        self.name = name
        self.mass = mass
        self.position = np.array(position, dtype=float)
        self.velocity = np.array(velocity, dtype=float)
        self.color = color
        self.base_radius = base_radius
        self.trail = []
        self.force_vector = np.array([0.0, 0.0])
        self.orbital_distance = np.linalg.norm(position)
        self.max_trail_length = self.calculate_trail_length()
        
    def calculate_forces(self, bodies: List['CelestialBody']):
        total_force = np.array([0.0, 0.0])
        for body in bodies:
            if body != self:
                r_vec = body.position - self.position
                r_mag = np.linalg.norm(r_vec)
                
                if r_mag > 0:
                    softening = 1e4
                    r_mag_soft = math.sqrt(r_mag**2 + softening**2)
                    force_mag = G * self.mass * body.mass / (r_mag_soft**2)
                    force_vec = force_mag * r_vec / r_mag_soft
                    total_force += force_vec
        
        self.force_vector = total_force
    
    def calculate_trail_length(self):
        orbit_length = 2 * math.pi * (self.orbital_distance if self.orbital_distance > 0 else AU)
        base_orbit_length = 2 * math.pi * AU
        ratio = orbit_length / base_orbit_length
        trail_length = int(100 + 700 * min(1.0, ratio / 10))
        return trail_length
        
    def get_screen_pos(self, offset_x, offset_y, zoom, pixel_scale, display_scale=1.0) -> Tuple[int, int]:
        sx = int(self.position[0] * display_scale * pixel_scale * zoom + offset_x)
        sy = int(self.position[1] * display_scale * pixel_scale * zoom + offset_y)
        return sx, sy

    def get_draw_radius(self, zoom, display_scale=1.0) -> int:
        scaled_radius = max(2, int(self.base_radius * zoom * display_scale))
        return scaled_radius

    def get_velocity_tip_pos(self, sx, sy, zoom, pixel_scale, display_scale=1.0) -> Tuple[int, int]:
        vel_scale = VELOCITY_VISUAL_SCALE * zoom * (pixel_scale / (250/AU)) * display_scale
        ex = int(sx + self.velocity[0] * vel_scale)
        ey = int(sy + self.velocity[1] * vel_scale)
        return ex, ey
        
    def update_trail(self):
        self.trail.append(self.position.copy())
        if len(self.trail) > self.max_trail_length:
            self.trail.pop(0)
    
    def update(self, bodies: List['CelestialBody'], dt: float):
        total_force = np.array([0.0, 0.0])
        for body in bodies:
            if body != self:
                r_vec = body.position - self.position
                r_mag = np.linalg.norm(r_vec)
                
                if r_mag > 0:
                    softening = 1e6
                    r_mag_soft = math.sqrt(r_mag**2 + softening**2)
                    force_mag = G * self.mass * body.mass / (r_mag_soft**2)
                    force_vec = force_mag * r_vec / r_mag_soft
                    total_force += force_vec
        
        self.force_vector = total_force
        acceleration = total_force / self.mass
        self.velocity += acceleration * dt
        self.position += self.velocity * dt

class SolarSystemSim:
    def __init__(self):
        pygame.init()
        self.base_width, self.base_height = 1600, 900
        self.width, self.height = self.base_width, self.base_height
        os.environ['SDL_VIDEO_CENTERED'] = '1'
        
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption("Solar System Simulator")
        self.clock = pygame.time.Clock()
        
        self.manager = pygame_gui.UIManager((self.width, self.height))
        
        # Коэффициенты масштабирования
        self.scale_factor = 1.0

        # Шрифты
        self.font_scale_factor = 1.0
        self.update_fonts()
        
        # Состояние
        self.bodies = []
        self.paused = False
        self.show_trails = True
        self.show_vectors = True 
        self.time_scale = 1.0
        
        # Камера
        self.offset_x = self.width // 2
        self.offset_y = self.height // 2
        self.zoom = 1.0
        self.min_zoom = 0.05
        self.max_zoom = 5.0
        
        # Анимация камеры
        self.camera_target_x = self.offset_x
        self.camera_target_y = self.offset_y
        self.is_camera_moving = False
        self.camera_speed = 0.08
        
        # Текущий пресет и масштабы отображения для каждого пресета
        self.current_preset = "Solar System"
        self.preset_pixel_scales = {
            "Solar System": 400 / AU,
            "Sun Earth Moon": 400 / AU,
            "Four random bodies": 400 / AU,
            "Four Star Ballet": 400 / AU,
            "Empty": 250 / AU
        }
        
        # Информационная панель
        self.show_info_panel = False
        self.info_panel_alpha = 0  # Альфа-канал для анимации
        self.info_panel_animation_speed = 0.15
        self.info_panel_rect = None  # Будет установлено при показе
        
        # Состояние кнопки "i"
        self.info_button_hovered = False
        self.info_button_rect = pygame.Rect(20, 20, 40, 40)
        
        # Состояние кнопки закрытия информационной панели
        self.info_close_button_hovered = False
        
        # Для правильного zoom (зум к центру экрана)
        self.last_zoom = self.zoom
        self.zoom_center_x = self.width // 2
        self.zoom_center_y = self.height // 2
        
        self.interaction_mode = 'idle'
        self.last_mouse_pos = (0, 0)
        self.active_body = None 
        
        # Звезды
        self.stars = [Star(self.width, self.height) for _ in range(300)]
        
        # UI элементы
        self.selected_body = None
        self.edit_panel = None
        self.ui_elements = []
        
        # Сообщения о столкновениях
        self.collision_messages = []
        
        self.mass_entry = None
        self.speed_entry = None
        self.vx_entry = None
        self.vy_entry = None
        self.delete_btn = None
        
        self.presets = {
            "Solar System": self.create_solar_system_data,
            "Sun Earth Moon": self.create_sun_earth_moon_data_MODIFIED,
            "Four Star Ballet": self.create_four_star_ballet_data,
            "Four random bodies": self.create_chaos_data,
            "Custom": self.create_empty_data
        }
        
        self.create_ui()
        self.load_preset("Solar System")
        
    def check_collisions(self):
        i = 0
        while i < len(self.bodies):
            body1 = self.bodies[i]
            j = i + 1
            while j < len(self.bodies):
                body2 = self.bodies[j]
                
                # Расстояние между центрами
                distance = np.linalg.norm(body1.position - body2.position)
                
                # Определяем радиусы для столкновения (используем базовый радиус для сравнения)
                collision_threshold = (body1.base_radius + body2.base_radius) * 1e9
                
                if distance < collision_threshold:
                    # Определяем меньшее тело
                    if body1.mass < body2.mass:
                        smaller, larger = body1, body2
                        smaller_idx, larger_idx = i, j
                    else:
                        smaller, larger = body2, body1
                        smaller_idx, larger_idx = j, i
                    
                    # Создаем сообщение о столкновении
                    message_text = f"{smaller.name} collided into {larger.name}"
                    
                    # Добавляем сообщение в начало списка
                    self.collision_messages.insert(0, {
                        'text': message_text,
                        'alpha': 255,
                        'start_time': pygame.time.get_ticks(),
                        'duration': 3000  # 3 секунды
                    })
                    
                    # Удаляем только меньшее тело
                    self.bodies.pop(smaller_idx)
                    
                    # Закрываем панель редактирования если удаленное тело было выбрано
                    if self.selected_body == smaller:
                        self.close_edit_panel()
                    
                    # Прерываем внутренний цикл и начинаем проверку заново
                    break
                
                j += 1
            else:
                i += 1
                continue
            # Если было столкновение, начинаем проверку заново
            continue
    
    def draw_collision_messages(self):
        """Рисует сообщения о столкновениях в правом нижнем углу"""
        current_time = pygame.time.get_ticks()
        
        # Обновляем и удаляем старые сообщения
        i = 0
        while i < len(self.collision_messages):
            msg = self.collision_messages[i]
            elapsed = current_time - msg['start_time']
            
            if elapsed >= msg['duration']:
                self.collision_messages.pop(i)
                continue
            
            # Вычисляем прозрачность (fadeout)
            fade_time = msg['duration'] - 1000  # начинаем fadeout за 1 секунду до конца
            if elapsed > fade_time:
                msg['alpha'] = int(255 * (1 - (elapsed - fade_time) / 1000))
            
            # Позиция сообщения (правая нижняя часть экрана)
            message_y = self.height - 50 - (i * 30)
            
            # Создаем поверхность для текста с альфа-каналом
            font_size = max(12, int(14 * self.font_scale_factor))
            font = pygame.font.SysFont('Arial', font_size)
            text_surface = font.render(msg['text'], True, (255, 255, 255))
            
            # Создаем новую поверхность с альфа-каналом
            alpha_surface = pygame.Surface(text_surface.get_size(), pygame.SRCALPHA)
            alpha_surface.blit(text_surface, (0, 0))
            alpha_surface.set_alpha(msg['alpha'])
            
            # Позиционируем текст
            text_x = self.width - text_surface.get_width() - 20
            self.screen.blit(alpha_surface, (text_x, message_y))
            
            i += 1

    def update_fonts(self):
        font_scale = max(0.5, min(2.0, self.scale_factor))
        self.font_scale_factor = font_scale
        
        base_font_name = 16
        base_font_title = 36
        base_font_subtitle = 24
        base_font_info = 18
        
        self.font_name = pygame.font.SysFont('Arial', int(base_font_name * font_scale))
        self.font_title = pygame.font.SysFont('Arial', int(base_font_title * font_scale), bold=True)
        self.font_subtitle = pygame.font.SysFont('Arial', int(base_font_subtitle * font_scale))
        self.font_info = pygame.font.SysFont('Arial', int(base_font_info * font_scale))

    def get_current_pixel_scale(self):
        return self.preset_pixel_scales.get(self.current_preset, 250/AU)
        
    def create_ui(self):
        self.manager.clear_and_reset()
        self.ui_elements = []
        
        panel_width = int(320 * self.scale_factor)
        panel_x = int(self.width - panel_width - 20 * self.scale_factor)
        panel_y = int(120 * self.scale_factor)
        panel_height = int(510 * self.scale_factor)
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height) 
        
        self.main_panel = pygame_gui.elements.UIPanel(
            relative_rect=panel_rect, manager=self.manager
        )
        self.ui_elements.append(self.main_panel)
        
        content_width = panel_width - int(40 * self.scale_factor)
        y_offset = int(15 * self.scale_factor)
        
        # Заголовок
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(30 * self.scale_factor)),
            text="SIMULATION CONTROL", manager=self.manager, container=self.main_panel
        )
        y_offset += int(40 * self.scale_factor)
        
        #Пресеты
        self.add_separator(y_offset)
        y_offset += int(15 * self.scale_factor)
        
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(20 * self.scale_factor)),
            text="Load Preset:", manager=self.manager, container=self.main_panel
        )
        y_offset += int(25 * self.scale_factor)
        
        self.preset_dropdown = pygame_gui.elements.UIDropDownMenu(
            options_list=list(self.presets.keys()),
            starting_option="Solar System",
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(30 * self.scale_factor)),
            manager=self.manager, container=self.main_panel
        )
        self.ui_elements.append(self.preset_dropdown)
        y_offset += int(40 * self.scale_factor)

        self.add_body_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(40 * self.scale_factor)),
            text="Add Random Planet", manager=self.manager, container=self.main_panel
        )
        self.ui_elements.append(self.add_body_btn)
        y_offset += int(50 * self.scale_factor)
        
        #Время
        self.add_separator(y_offset)
        y_offset += int(15 * self.scale_factor)
        
        self.play_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(40 * self.scale_factor)),
            text="PAUSE" if not self.paused else "RESUME",
            manager=self.manager, container=self.main_panel
        )
        self.ui_elements.append(self.play_btn)
        y_offset += int(50 * self.scale_factor)
        
        self.time_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(25 * self.scale_factor)),
            text=f"Speed: {self.time_scale:.1f}x",
            manager=self.manager, container=self.main_panel
        )
        self.ui_elements.append(self.time_label)
        y_offset += int(30 * self.scale_factor)
        
        self.time_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(25 * self.scale_factor)),
            start_value=self.time_scale, value_range=(0.0, 5.0),
            manager=self.manager, container=self.main_panel
        )
        self.ui_elements.append(self.time_slider)
        y_offset += int(40 * self.scale_factor)
        
        #Вид
        self.add_separator(y_offset)
        y_offset += int(15 * self.scale_factor)
        
        self.zoom_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(25 * self.scale_factor)),
            text=f"Zoom: {self.zoom:.2f}x",
            manager=self.manager, container=self.main_panel
        )
        self.ui_elements.append(self.zoom_label)
        y_offset += int(30 * self.scale_factor)
        
        self.zoom_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(25 * self.scale_factor)),
            start_value=self.zoom, value_range=(self.min_zoom, self.max_zoom),
            manager=self.manager, container=self.main_panel
        )
        self.ui_elements.append(self.zoom_slider)
        y_offset += int(40 * self.scale_factor)
        
        btn_width = (content_width - int(10 * self.scale_factor)) // 2
        self.trails_check = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, btn_width, int(35 * self.scale_factor)),
            text="Trails: ON" if self.show_trails else "OFF",
            manager=self.manager, container=self.main_panel
        )
        self.ui_elements.append(self.trails_check)
        
        self.vectors_check = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(int(20 * self.scale_factor) + btn_width + int(10 * self.scale_factor), y_offset, btn_width, int(35 * self.scale_factor)),
            text="Vectors: ON" if self.show_vectors else "OFF",
            manager=self.manager, container=self.main_panel
        )
        self.ui_elements.append(self.vectors_check)
        
        y_offset += int(45 * self.scale_factor)
        
        # Кнопка для перемещения камеры в центр масс
        self.center_camera_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(40 * self.scale_factor)),
            text="Move To Center Of Mass",
            manager=self.manager, container=self.main_panel
        )
        self.ui_elements.append(self.center_camera_btn)
        
        if self.selected_body:
            self.create_edit_panel()

    def add_separator(self, y_pos):
        pygame_gui.elements.UIPanel(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_pos, 
                                    int(280 * self.scale_factor), int(2 * self.scale_factor)),
            manager=self.manager, container=self.main_panel
        )

    def draw_info_panel(self):
        if not self.show_info_panel and self.info_panel_alpha <= 0:
            return
        
        #альфа-канал для анимации
        if self.show_info_panel:
            self.info_panel_alpha = min(255, self.info_panel_alpha + 255 * self.info_panel_animation_speed)
        else:
            self.info_panel_alpha = max(0, self.info_panel_alpha - 255 * self.info_panel_animation_speed)
        
        if self.info_panel_alpha <= 0:
            return
        
        panel_width = int(500 * self.scale_factor)
        panel_height = int(200 * self.scale_factor)
        panel_x = self.width // 2 - panel_width // 2
        panel_y = self.height // 2 - panel_height // 2
        
        # Эффект появления (увеличение)
        scale_factor_anim = 0.7 + 0.3 * (self.info_panel_alpha / 255)
        current_width = int(panel_width * scale_factor_anim)
        current_height = int(panel_height * scale_factor_anim)
        current_x = self.width // 2 - current_width // 2
        current_y = self.height // 2 - current_height // 2
        
        self.info_panel_rect = pygame.Rect(current_x, current_y, current_width, current_height)
        
        # Полупрозрачный фон
        overlay_alpha = int(128 * (self.info_panel_alpha / 255))
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, overlay_alpha))
        self.screen.blit(overlay, (0, 0))
        
        # Основная панель
        panel_surface = pygame.Surface((current_width, current_height), pygame.SRCALPHA)
        panel_color = (30, 35, 50, self.info_panel_alpha)
        border_color = (60, 70, 100, self.info_panel_alpha)
        
        border_radius = int(12 * self.scale_factor * scale_factor_anim)
        border_width = int(3 * self.scale_factor * scale_factor_anim)
        
        pygame.draw.rect(panel_surface, panel_color, (0, 0, current_width, current_height), 
                        border_radius=border_radius)
        pygame.draw.rect(panel_surface, border_color, (0, 0, current_width, current_height), 
                        border_width, border_radius=border_radius)
        
        # Заголовок
        title_font_size = max(18, int(24 * self.font_scale_factor * scale_factor_anim))
        title_font = pygame.font.SysFont('Arial', title_font_size)
        title_text = title_font.render("CONTROLS GUIDE", True, (255, 255, 255))
        title_alpha = int(self.info_panel_alpha * 0.8)
        title_text.set_alpha(title_alpha)
        title_x = current_width // 2 - title_text.get_width() // 2
        title_y = int(20 * self.scale_factor * scale_factor_anim)
        panel_surface.blit(title_text, (title_x, title_y))
        
        close_rect_size = int(25 * self.scale_factor * scale_factor_anim)
        close_rect_x = current_width - close_rect_size - int(15 * self.scale_factor * scale_factor_anim)
        close_rect_y = int(15 * self.scale_factor * scale_factor_anim)
        
        self.close_button_rect = pygame.Rect(
            current_x + close_rect_x,
            current_y + close_rect_y,
            close_rect_size,
            close_rect_size
        )
        
        # Цвет кнопки закрытия зависит от наведения
        close_color = (255, 100, 100) if self.info_close_button_hovered else (200, 80, 80)
        close_color_with_alpha = (*close_color, self.info_panel_alpha)
        
        close_surface = pygame.Surface((close_rect_size, close_rect_size), pygame.SRCALPHA)
        close_border_radius = int(4 * self.scale_factor * scale_factor_anim)
        pygame.draw.rect(close_surface, close_color_with_alpha, (0, 0, close_rect_size, close_rect_size), 
                        border_radius=close_border_radius)
        
        cross_margin = int(7.5 * self.scale_factor * scale_factor_anim)
        cross_width = int(2 * self.scale_factor * scale_factor_anim)
        
        pygame.draw.line(close_surface, (255, 255, 255, self.info_panel_alpha), 
                        (cross_margin, cross_margin), 
                        (close_rect_size - cross_margin, close_rect_size - cross_margin), 
                        cross_width)
        pygame.draw.line(close_surface, (255, 255, 255, self.info_panel_alpha), 
                        (close_rect_size - cross_margin, cross_margin), 
                        (cross_margin, close_rect_size - cross_margin), 
                        cross_width)
        
        panel_surface.blit(close_surface, (close_rect_x, close_rect_y))
        
        # Содержимое
        lines = [
            "Click on an object to change its parameters",
            "Drag an object to move it",
            "Drag a velocity vector to change its speed and direction",
            "Use mouse wheel to zoom in/out"
        ]
        
        y_offset = int(60 * self.scale_factor * scale_factor_anim)
        for line in lines:
            if line:
                color = (200, 220, 255) if line.startswith("•") else (200, 200, 200)
                font_size = max(12, int(18 * self.font_scale_factor * scale_factor_anim))
                font = pygame.font.SysFont('Arial', font_size)
                text_alpha = int(self.info_panel_alpha * 0.9)
                text = font.render(line, True, color)
                text.set_alpha(text_alpha)
                text_x = int(30 * self.scale_factor * scale_factor_anim)
                panel_surface.blit(text, (text_x, y_offset))
            y_offset += int(30 * self.scale_factor * scale_factor_anim)
        
        self.screen.blit(panel_surface, (current_x, current_y))

    def create_edit_panel(self):
        if self.edit_panel:
            self.edit_panel.kill()
            if self.edit_panel in self.ui_elements:
                self.ui_elements.remove(self.edit_panel)
        
        self.mass_entry = None
        self.speed_entry = None
        self.vx_entry = None
        self.vy_entry = None
        self.delete_btn = None
        self.name_entry = None
        
        if not self.selected_body:
            return

        body = self.selected_body
        
        panel_width = int(300 * self.scale_factor)
        panel_height = int(400 * self.scale_factor)
        panel_rect = pygame.Rect(int(20 * self.scale_factor), 
                                self.height - panel_height - int(20 * self.scale_factor), 
                                panel_width, panel_height)
        
        self.edit_panel = pygame_gui.elements.UIPanel(
            relative_rect=panel_rect, manager=self.manager
        )
        self.ui_elements.append(self.edit_panel)
        
        content_width = panel_width - int(40 * self.scale_factor)
        y_offset = int(15 * self.scale_factor)
        
        # Заголовок
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(30 * self.scale_factor)),
            text=f"EDIT: {body.name.upper()}",
            manager=self.manager, container=self.edit_panel
        )
        y_offset += int(40 * self.scale_factor)
        
        # Поле для изменения имени
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(20 * self.scale_factor)),
            text=f"Name:", manager=self.manager, container=self.edit_panel
        )
        y_offset += int(20 * self.scale_factor)
        self.name_entry = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(30 * self.scale_factor)),
            manager=self.manager, container=self.edit_panel
        )
        self.name_entry.set_text(f"{body.name}")
        self.name_entry.set_text_length_limit(15)
        y_offset += int(40 * self.scale_factor)
        
        # Mass
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(20 * self.scale_factor)),
            text=f"Mass (kg):", manager=self.manager, container=self.edit_panel
        )
        y_offset += int(20 * self.scale_factor)
        self.mass_entry = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(30 * self.scale_factor)),
            manager=self.manager, container=self.edit_panel
        )
        self.mass_entry.set_text(f"{body.mass:.2e}")
        y_offset += int(40 * self.scale_factor)
        
        speed = np.linalg.norm(body.velocity)
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(20 * self.scale_factor)),
            text=f"Speed (m/s):", manager=self.manager, container=self.edit_panel
        )
        y_offset += int(20 * self.scale_factor)
        self.speed_entry = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(30 * self.scale_factor)),
            manager=self.manager, container=self.edit_panel
        )
        self.speed_entry.set_text(f"{speed:.1f}")
        y_offset += int(40 * self.scale_factor)

        # Components (для точности)
        half_w = (content_width - int(10 * self.scale_factor)) // 2
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, half_w, int(20 * self.scale_factor)),
            text="Vel X:", manager=self.manager, container=self.edit_panel
        )
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(int(20 * self.scale_factor) + half_w + int(10 * self.scale_factor), 
                                    y_offset, half_w, int(20 * self.scale_factor)),
            text="Vel Y:", manager=self.manager, container=self.edit_panel
        )
        y_offset += int(20 * self.scale_factor)
        
        self.vx_entry = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, half_w, int(30 * self.scale_factor)),
            manager=self.manager, container=self.edit_panel
        )
        self.vx_entry.set_text(f"{body.velocity[0]:.1f}")
        
        self.vy_entry = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect(int(20 * self.scale_factor) + half_w + int(10 * self.scale_factor), 
                                    y_offset, half_w, int(30 * self.scale_factor)),
            manager=self.manager, container=self.edit_panel
        )
        self.vy_entry.set_text(f"{body.velocity[1]:.1f}")
        y_offset += int(40 * self.scale_factor)
        
        self.delete_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(int(20 * self.scale_factor), y_offset, content_width, int(40 * self.scale_factor)),
            text=f"DELETE BODY",
            manager=self.manager, container=self.edit_panel
        )
        
    def close_edit_panel(self):
        if self.edit_panel:
            if self.edit_panel in self.ui_elements:
                self.ui_elements.remove(self.edit_panel)
            self.edit_panel.kill()
            self.edit_panel = None
            self.selected_body = None
            self.mass_entry = None
            self.speed_entry = None
            self.vx_entry = None
            self.vy_entry = None
            self.delete_btn = None

    def calculate_center_of_mass(self) -> Tuple[float, float]:
        if not self.bodies:
            return 0.0, 0.0
        
        total_mass = 0.0
        center_x, center_y = 0.0, 0.0
        
        for body in self.bodies:
            total_mass += body.mass
            center_x += body.position[0] * body.mass
            center_y += body.position[1] * body.mass
        
        if total_mass > 0:
            center_x /= total_mass
            center_y /= total_mass
        
        return center_x, center_y
    
    def center_camera_on_com(self):
        com_x, com_y = self.calculate_center_of_mass()
        pixel_scale = self.get_current_pixel_scale()
        
        self.camera_target_x = int(self.width // 2 - com_x * pixel_scale * self.zoom)
        self.camera_target_y = int(self.height // 2 - com_y * pixel_scale * self.zoom)
        
        self.is_camera_moving = True
    
    def update_camera_animation(self):
        if self.is_camera_moving:
            dx = self.camera_target_x - self.offset_x
            dy = self.camera_target_y - self.offset_y
            
            if abs(dx) < 1 and abs(dy) < 1:
                self.offset_x = self.camera_target_x
                self.offset_y = self.camera_target_y
                self.is_camera_moving = False
            else:
                self.offset_x += dx * self.camera_speed
                self.offset_y += dy * self.camera_speed

    def create_empty_data(self):
        return []

    def create_solar_system_data(self):
        # Реальные орбитальные параметры планет (эксцентриситет и наклонение упрощены)
        bodies = []
        
        # Солнце
        bodies.append(CelestialBody(
            "Sun", 1.989e30, (0, 0), (0, 0), 
            (255, 220, 80), 30
        ))
        
        # Меркурий
        mercury_eccentricity = 0.2056
        mercury_semi_major = 0.387 * AU
        mercury_perihelion = mercury_semi_major * (1 - mercury_eccentricity)
        mercury_vel_peri = math.sqrt(G * 1.989e30 * (1 + mercury_eccentricity) / mercury_perihelion)
        
        bodies.append(CelestialBody(
            "Mercury", 3.301e23, 
            (mercury_perihelion, 0), 
            (0, mercury_vel_peri), 
            (160, 160, 160), 4
        ))
        
        # Венера
        venus_eccentricity = 0.0067
        venus_semi_major = 0.723 * AU
        venus_perihelion = venus_semi_major * (1 - venus_eccentricity)
        venus_vel_peri = math.sqrt(G * 1.989e30 * (1 + venus_eccentricity) / venus_perihelion)
        
        bodies.append(CelestialBody(
            "Venus", 4.867e24,
            (venus_perihelion, 0),
            (0, venus_vel_peri),
            (220, 180, 140), 7
        ))
        
        # Земля
        earth_eccentricity = 0.0167
        earth_semi_major = 1.0 * AU
        earth_perihelion = earth_semi_major * (1 - earth_eccentricity)
        earth_vel_peri = math.sqrt(G * 1.989e30 * (1 + earth_eccentricity) / earth_perihelion)
        
        bodies.append(CelestialBody(
            "Earth", 5.972e24,
            (earth_perihelion, 0),
            (0, earth_vel_peri),
            (100, 150, 255), 7
        ))
        
        # Марс
        mars_eccentricity = 0.0935
        mars_semi_major = 1.524 * AU
        mars_perihelion = mars_semi_major * (1 - mars_eccentricity)
        mars_vel_peri = math.sqrt(G * 1.989e30 * (1 + mars_eccentricity) / mars_perihelion)
        
        bodies.append(CelestialBody(
            "Mars", 6.417e23,
            (mars_perihelion, 0),
            (0, mars_vel_peri),
            (255, 80, 80), 5
        ))
        
        # Юпитер
        jupiter_eccentricity = 0.0489
        jupiter_semi_major = 5.203 * AU
        jupiter_perihelion = jupiter_semi_major * (1 - jupiter_eccentricity)
        jupiter_vel_peri = math.sqrt(G * 1.989e30 * (1 + jupiter_eccentricity) / jupiter_perihelion)
        
        bodies.append(CelestialBody(
            "Jupiter", 1.898e27,
            (jupiter_perihelion, 0),
            (0, jupiter_vel_peri),
            (200, 180, 150), 16
        ))
        
        # Сатурн
        saturn_eccentricity = 0.0565
        saturn_semi_major = 9.537 * AU
        saturn_perihelion = saturn_semi_major * (1 - saturn_eccentricity)
        saturn_vel_peri = math.sqrt(G * 1.989e30 * (1 + saturn_eccentricity) / saturn_perihelion)
        
        bodies.append(CelestialBody(
            "Saturn", 5.683e26,
            (saturn_perihelion, 0),
            (0, saturn_vel_peri),
            (230, 200, 100), 14
        ))
        
        # Уран
        uranus_eccentricity = 0.0457
        uranus_semi_major = 19.191 * AU
        uranus_perihelion = uranus_semi_major * (1 - uranus_eccentricity)
        uranus_vel_peri = math.sqrt(G * 1.989e30 * (1 + uranus_eccentricity) / uranus_perihelion)
        
        bodies.append(CelestialBody(
            "Uranus", 8.681e25,
            (uranus_perihelion, 0),
            (0, uranus_vel_peri),
            (150, 220, 255), 12
        ))
        
        # Нептун
        neptune_eccentricity = 0.0113
        neptune_semi_major = 30.069 * AU
        neptune_perihelion = neptune_semi_major * (1 - neptune_eccentricity)
        neptune_vel_peri = math.sqrt(G * 1.989e30 * (1 + neptune_eccentricity) / neptune_perihelion)
        
        bodies.append(CelestialBody(
            "Neptune", 1.024e26,
            (neptune_perihelion, 0),
            (0, neptune_vel_peri),
            (80, 120, 255), 12
        ))
        
        return bodies

    def create_sun_earth_moon_data_MODIFIED(self):
        sun_mass = 1.989e30
        earth_mass = 5.972e24 * 1500 
        moon_mass = 7.348e22
        
        earth_orbit_radius = 1.0 * AU
        earth_orbital_speed = math.sqrt(G * sun_mass / earth_orbit_radius)
        
        moon_earth_distance = 0.05 * AU 
        moon_orbital_speed_rel_earth = math.sqrt(G * earth_mass / moon_earth_distance)
        
        bodies = []
        
        earth_pos = np.array([earth_orbit_radius, 0.0], dtype=float)
        earth_vel = np.array([0.0, earth_orbital_speed], dtype=float)

        moon_pos_rel_earth = np.array([0.0, moon_earth_distance], dtype=float)
        moon_orbital_vel_rel_earth = np.array([moon_orbital_speed_rel_earth, 0.0], dtype=float)
        
        moon_pos_absolute = earth_pos + moon_pos_rel_earth
        moon_vel_absolute = earth_vel + moon_orbital_vel_rel_earth
        
        bodies.append(CelestialBody(
            "Sun", sun_mass, (0, 0), (0, 0), 
            (255, 220, 80), 60
        ))
        
        bodies.append(CelestialBody(
            "Earth", earth_mass, tuple(earth_pos), tuple(earth_vel), 
            (100, 150, 255), 12
        ))
        
        bodies.append(CelestialBody(
            "Moon", moon_mass, tuple(moon_pos_absolute), tuple(moon_vel_absolute), 
            (200, 200, 200), 6
        ))
        
        self._correct_center_of_mass_drift_for_bodies(bodies)
        
        return bodies

    def _correct_center_of_mass_drift_for_bodies(self, bodies):
        if not bodies:
            return
        
        total_mass = 0.0
        center_of_mass = np.zeros(2, dtype=float)
        total_momentum = np.zeros(2, dtype=float)
        
        for body in bodies:
            total_mass += body.mass
            center_of_mass += body.position * body.mass
            total_momentum += body.velocity * body.mass
        
        if total_mass > 0:
            center_of_mass /= total_mass
            system_velocity = total_momentum / total_mass
            
            for body in bodies:
                body.position -= center_of_mass
                body.velocity -= system_velocity

    def create_chaos_data(self):
        bodies = []
        for i in range(4):
            pos = (random.uniform(-1.5*AU, 1.5*AU), random.uniform(-1.5*AU, 1.5*AU))
            vel = (random.uniform(-10000, 10000), random.uniform(-10000, 10000))
            bodies.append(CelestialBody(f"Body {i}", random.uniform(1e28, 9e28), pos, vel, 
                                        (random.randint(100,255), random.randint(100,255), 255), 15))
        return bodies

    def create_four_star_ballet_data(self):
        m = 1e30
        r = 1.2 * AU
        exact_v = math.sqrt(G * m / r * (1/math.sqrt(2) + 0.5)) * 0.98
        
        bodies = []
        
        configs = [
            (r, 0, 0, exact_v, (255, 100, 100), "Star 1"),
            (0, r, -exact_v, 0, (100, 255, 100), "Star 2"),
            (-r, 0, 0, -exact_v, (100, 100, 255), "Star 3"), 
            (0, -r, exact_v, 0, (255, 255, 100), "Star 4")
        ]
        
        for px, py, vx, vy, color, name in configs:
            bodies.append(CelestialBody(
                name, m, 
                (px, py), (vx, vy), 
                color, 10
            ))
        
        self._correct_center_of_mass_drift_for_bodies(bodies)
        return bodies

    def add_random_body(self):
        dist = random.uniform(1.2*AU, 4.0*AU)
        angle = random.uniform(0, 2*math.pi)
        pos_x = math.cos(angle) * dist
        pos_y = math.sin(angle) * dist
        v = math.sqrt(G * 1.989e30 / dist)
        vel_x = -math.sin(angle) * v * random.uniform(0.8, 1.2)
        vel_y = math.cos(angle) * v * random.uniform(0.8, 1.2)
        color = (random.randint(100,255), random.randint(100,255), random.randint(100,255))
        
        self.bodies.append(CelestialBody(
            f"Planet {len(self.bodies)}", random.uniform(1e23, 5e25), 
            (pos_x, pos_y), (vel_x, vel_y), color, random.randint(4, 9)
        ))

    def load_preset(self, preset_name):
        self.bodies = []
        self.collision_messages = []  # Очищаем сообщения о столкновениях
        self.current_preset = preset_name
        
        if preset_name in self.presets:
            self.bodies = self.presets[preset_name]()
            
            # Сброс камеры и состояния
            self.offset_x = self.width // 2
            self.offset_y = self.height // 2
            self.camera_target_x = self.offset_x
            self.camera_target_y = self.offset_y
            self.is_camera_moving = False
            self.paused = True

            # Универсальные настройки для всех пресетов
            if preset_name == "Solar System":
                self.zoom = 0.8
            elif preset_name == "Sun Earth Moon":
                self.zoom = 0.6
            elif preset_name == "Four random bodies":
                self.zoom = 0.8
            elif preset_name == "Four Star Ballet":
                self.zoom = 0.5
                self.time_scale = 3.0
            elif preset_name == "Empty":
                self.zoom = 1.0
                
            # Обновление UI элементов
            if hasattr(self, 'play_btn'):
                self.play_btn.set_text("PAUSE" if not self.paused else "RESUME")
            if hasattr(self, 'zoom_slider'):
                self.zoom_slider.set_current_value(self.zoom)
                self.zoom_label.set_text(f"Zoom: {self.zoom:.2f}x")
            if hasattr(self, 'time_slider'):
                self.time_slider.set_current_value(self.time_scale)
                self.time_label.set_text(f"Speed: {self.time_scale:.1f}x")
                
            self.close_edit_panel()

    def is_mouse_over_ui(self, mouse_pos):
        for element in self.ui_elements:
            if element.rect.collidepoint(mouse_pos):
                return True
        return False

    def get_body_at_pos(self, mouse_pos) -> 'CelestialBody' or None:
        mx, my = mouse_pos
        pixel_scale = self.get_current_pixel_scale()
        
        for body in self.bodies:
            sx, sy = body.get_screen_pos(self.offset_x, self.offset_y, self.zoom, pixel_scale, 1.0)
            radius = body.get_draw_radius(self.zoom, 1.0)
            if math.hypot(mx - sx, my - sy) <= radius + 5: 
                return body
        return None

    def get_vector_tip_at_pos(self, mouse_pos) -> 'CelestialBody' or None:
        if not self.show_vectors:
            return None
            
        mx, my = mouse_pos
        hit_radius = max(6, min(15, 8 * self.zoom))
        pixel_scale = self.get_current_pixel_scale()
        
        for body in self.bodies:
            sx, sy = body.get_screen_pos(self.offset_x, self.offset_y, self.zoom, pixel_scale, 1.0)
            ex, ey = body.get_velocity_tip_pos(sx, sy, self.zoom, pixel_scale, 1.0)
            
            if math.hypot(ex - sx, ey - sy) < 2:
                continue
                
            if math.hypot(mx - ex, my - ey) <= hit_radius:
                return body
        return None

    def draw_arrow(self, start, end, color, width=3, zoom=1.0):
        pygame.draw.line(self.screen, color, start, end, width)
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        angle = math.atan2(dy, dx)
        arrow_length = 18 * zoom
        arrow_angle = math.pi / 6
        x1 = end[0] - arrow_length * math.cos(angle - arrow_angle)
        y1 = end[1] - arrow_length * math.sin(angle - arrow_angle)
        x2 = end[0] - arrow_length * math.cos(angle + arrow_angle)
        y2 = end[1] - arrow_length * math.sin(angle + arrow_angle)
        pygame.draw.line(self.screen, color, end, (x1, y1), width)
        pygame.draw.line(self.screen, color, end, (x2, y2), width)

    def draw_title_bar(self):
        title_width = int(600 * self.scale_factor)
        title_height = int(110 * self.scale_factor)
        title_x = self.width // 2 - title_width // 2
        title_y = int(20 * self.scale_factor)
        title_rect = pygame.Rect(title_x, title_y, title_width, title_height)
        
        border_radius = int(12 * self.scale_factor)
        border_width = int(2 * self.scale_factor)
        
        pygame.draw.rect(self.screen, (30, 35, 45), title_rect, border_radius=border_radius)
        pygame.draw.rect(self.screen, (60, 70, 90), title_rect, border_width, border_radius=border_radius)
        
        #уже масштабированные шрифты
        title_text = self.font_title.render("SOLAR SYSTEM SIMULATOR", True, (255, 255, 255))
        title_text_y = title_y + int(20 * self.scale_factor)
        self.screen.blit(title_text, (self.width // 2 - title_text.get_width() // 2, title_text_y))
        
        author_text = self.font_subtitle.render("by Galochkin Platon", True, (180, 200, 255))
        author_text_y = title_y + int(65 * self.scale_factor)
        self.screen.blit(author_text, (self.width // 2 - author_text.get_width() // 2, author_text_y))

    def handle_zoom_to_center(self, zoom_delta):
        old_zoom = self.zoom
        
        mouse_x, mouse_y = pygame.mouse.get_pos()
        
        if zoom_delta > 0:
            self.zoom *= 1.1
        else:
            self.zoom /= 1.1
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom))
        
        # Если zoom изменился
        if old_zoom != self.zoom:
            zoom_factor = self.zoom / old_zoom
            
            self.offset_x = mouse_x - (mouse_x - self.offset_x) * zoom_factor
            self.offset_y = mouse_y - (mouse_y - self.offset_y) * zoom_factor
            
            self.camera_target_x = self.offset_x
            self.camera_target_y = self.offset_y
            
            if hasattr(self, 'zoom_slider'):
                self.zoom_slider.set_current_value(self.zoom)
            if hasattr(self, 'zoom_label'):
                self.zoom_label.set_text(f"Zoom: {self.zoom:.2f}x")

    def handle_input(self):
        time_delta = self.clock.tick(60) / 1000.0
        mouse_pos = pygame.mouse.get_pos()
        pixel_scale = self.get_current_pixel_scale()
        
        # Обновление состояния наведения на кнопку "i"
        self.info_button_hovered = self.info_button_rect.collidepoint(mouse_pos) if hasattr(self, 'info_button_rect') else False
        
        # Обновление состояния наведения на кнопку закрытия информационной панели
        self.info_close_button_hovered = False
        if self.show_info_panel and hasattr(self, 'close_button_rect') and self.close_button_rect:
            self.info_close_button_hovered = self.close_button_rect.collidepoint(mouse_pos)
        
        if self.is_camera_moving:
            self.interaction_mode = 'idle'
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            self.manager.process_events(event)
            
            if event.type == pygame.VIDEORESIZE:
                new_width = max(1600, event.w)
                new_height = max(900, event.h)
                if event.w < 1600 or event.h < 900:
                    self.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
                    self.width, self.height = new_width, new_height
                else:
                    self.width, self.height = event.w, event.h
                
                width_scale = self.width / self.base_width
                height_scale = self.height / self.base_height
                self.scale_factor = min(width_scale, height_scale)
                
                self.update_fonts()
                self.manager = pygame_gui.UIManager((self.width, self.height))
                self.create_ui()
                self.stars = [Star(self.width, self.height) for _ in range(300)]
                self.offset_x = self.width // 2
                self.offset_y = self.height // 2
                self.camera_target_x = self.offset_x
                self.camera_target_y = self.offset_y
            
                self.info_button_rect = pygame.Rect(
                    int(20 * self.scale_factor),
                    int(20 * self.scale_factor),
                    int(40 * self.scale_factor),
                    int(40 * self.scale_factor)
                )

            elif event.type == pygame.MOUSEWHEEL:
                self.handle_zoom_to_center(event.y)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if hasattr(self, 'info_button_rect') and self.info_button_rect.collidepoint(mouse_pos):
                        self.show_info_panel = not self.show_info_panel
                        continue
                    
                    if self.show_info_panel and self.info_panel_alpha > 0 and hasattr(self, 'close_button_rect') and self.close_button_rect:
                        if self.close_button_rect.collidepoint(mouse_pos):
                            self.show_info_panel = False
                            continue
                    
                    if self.show_info_panel and hasattr(self, 'info_panel_rect') and self.info_panel_rect and self.info_panel_rect.collidepoint(mouse_pos):
                        continue
                    
                    if not self.is_mouse_over_ui(mouse_pos) and not self.is_camera_moving:
                        vector_body = self.get_vector_tip_at_pos(mouse_pos)
                        if vector_body:
                            self.interaction_mode = 'drag_vector'
                            self.active_body = vector_body
                            self.selected_body = vector_body
                            self.create_edit_panel() 
                            self.paused = True 
                            if hasattr(self, 'play_btn'):
                                self.play_btn.set_text("RESUME")
                        else:
                            clicked_body = self.get_body_at_pos(mouse_pos)
                            if clicked_body:
                                self.interaction_mode = 'drag_body'
                                self.active_body = clicked_body
                                self.selected_body = clicked_body
                                self.create_edit_panel()
                                self.paused = True 
                                if hasattr(self, 'play_btn'):
                                    self.play_btn.set_text("RESUME")
                            else:
                                self.interaction_mode = 'pan_camera'
                                self.last_mouse_pos = mouse_pos
                                self.close_edit_panel()
                    
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.interaction_mode = 'idle'
                    self.active_body = None
            
            elif event.type == pygame.MOUSEMOTION:
                if self.interaction_mode == 'pan_camera' and not self.is_camera_moving:
                    dx = mouse_pos[0] - self.last_mouse_pos[0]
                    dy = mouse_pos[1] - self.last_mouse_pos[1]
                    self.offset_x += dx
                    self.offset_y += dy
                    self.last_mouse_pos = mouse_pos
                    self.camera_target_x = self.offset_x
                    self.camera_target_y = self.offset_y
                
                elif self.interaction_mode == 'drag_body' and self.active_body and not self.is_camera_moving:
                    mx, my = mouse_pos
                    world_x = (mx - self.offset_x) / (pixel_scale * self.zoom)
                    world_y = (my - self.offset_y) / (pixel_scale * self.zoom)
                    
                    self.active_body.position = np.array([world_x, world_y])
                    self.active_body.trail = [] 

                elif self.interaction_mode == 'drag_vector' and self.active_body and not self.is_camera_moving:
                    bx, by = self.active_body.get_screen_pos(self.offset_x, self.offset_y, self.zoom, pixel_scale, 1.0)
                    
                    mx, my = mouse_pos
                    dx_screen = mx - bx
                    dy_screen = my - by
                    
                    base_scale = VELOCITY_VISUAL_SCALE * self.zoom * (pixel_scale / (250/AU))
                    
                    if base_scale > 0:
                        new_vx = dx_screen / base_scale
                        new_vy = dy_screen / base_scale
                        self.active_body.velocity = np.array([new_vx, new_vy])
                        
                    if hasattr(self, 'vx_entry') and self.vx_entry and hasattr(self, 'vy_entry') and self.vy_entry and hasattr(self, 'speed_entry') and self.speed_entry:
                        self.vx_entry.set_text(f"{new_vx:.1f}")
                        self.vy_entry.set_text(f"{new_vy:.1f}")
                        self.speed_entry.set_text(f"{np.linalg.norm([new_vx, new_vy]):.1f}")

            # Обработка клавиши Space для паузы
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                    if hasattr(self, 'play_btn'):
                        self.play_btn.set_text("PAUSE" if not self.paused else "RESUME")

            #UI EVENTS
            if event.type == pygame_gui.UI_BUTTON_PRESSED:
                if event.ui_element == self.play_btn:
                    self.paused = not self.paused
                    self.play_btn.set_text("PAUSE" if not self.paused else "RESUME")
                elif event.ui_element == self.add_body_btn:
                    self.add_random_body()
                elif event.ui_element == self.trails_check:
                    self.show_trails = not self.show_trails
                    self.trails_check.set_text("Trails: ON" if self.show_trails else "OFF")
                elif event.ui_element == self.vectors_check:
                    self.show_vectors = not self.show_vectors
                    self.vectors_check.set_text("Vectors: ON" if self.show_vectors else "OFF")
                elif hasattr(self, 'center_camera_btn') and event.ui_element == self.center_camera_btn:
                    self.center_camera_on_com()
                
                if hasattr(self, 'delete_btn') and self.delete_btn and event.ui_element == self.delete_btn:
                    if self.selected_body in self.bodies:
                        self.bodies.remove(self.selected_body)
                        self.close_edit_panel()
            
            elif event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
                if event.ui_element == self.preset_dropdown:
                    self.load_preset(event.text)

            elif event.type == pygame_gui.UI_TEXT_ENTRY_FINISHED:
                if self.selected_body:
                    try:
                        val = float(event.text.replace(',', '.'))
                        if hasattr(self, 'mass_entry') and event.ui_element == self.mass_entry:
                            self.selected_body.mass = val
                        elif hasattr(self, 'vx_entry') and event.ui_element == self.vx_entry:
                            self.selected_body.velocity[0] = val
                            v = np.linalg.norm(self.selected_body.velocity)
                            if hasattr(self, 'speed_entry') and self.speed_entry: 
                                self.speed_entry.set_text(f"{v:.1f}")
                        elif hasattr(self, 'vy_entry') and event.ui_element == self.vy_entry:
                            self.selected_body.velocity[1] = val
                            v = np.linalg.norm(self.selected_body.velocity)
                            if hasattr(self, 'speed_entry') and self.speed_entry: 
                                self.speed_entry.set_text(f"{v:.1f}")
                        elif hasattr(self, 'speed_entry') and event.ui_element == self.speed_entry:
                            current_v = self.selected_body.velocity
                            angle = math.atan2(current_v[1], current_v[0])
                            self.selected_body.velocity[0] = math.cos(angle) * val
                            self.selected_body.velocity[1] = math.sin(angle) * val
                            if hasattr(self, 'vx_entry') and self.vx_entry: 
                                self.vx_entry.set_text(f"{self.selected_body.velocity[0]:.1f}")
                            if hasattr(self, 'vy_entry') and self.vy_entry: 
                                self.vy_entry.set_text(f"{self.selected_body.velocity[1]:.1f}")
                    except ValueError:
                        if hasattr(self, 'name_entry') and event.ui_element == self.name_entry:
                            new_name = event.text.strip()
                            if new_name:
                                self.selected_body.name = new_name
                                self.create_edit_panel()
                        else:
                            print("Invalid number input")
                            self.create_edit_panel()

            elif event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
                if event.ui_element == self.time_slider:
                    self.time_scale = float(event.value)
                    self.time_label.set_text(f"Speed: {self.time_scale:.1f}x")
                elif event.ui_element == self.zoom_slider:
                    old_zoom = self.zoom
                    self.zoom = float(event.value)
                    if old_zoom != self.zoom:
                        zoom_factor = self.zoom / old_zoom
                        center_x = self.width // 2
                        center_y = self.height // 2
                        self.offset_x = center_x - (center_x - self.offset_x) * zoom_factor
                        self.offset_y = center_y - (center_y - self.offset_y) * zoom_factor
                        self.zoom_label.set_text(f"Zoom: {self.zoom:.2f}x")
        
        self.manager.update(time_delta)
        return True

    def draw(self):
        self.screen.fill((5, 8, 15))
        
        # Звезды
        for star in self.stars:
            sx = (star.x + self.offset_x * 0.05 * star.z) % self.width
            sy = (star.y + self.offset_y * 0.05 * star.z) % self.height
            pygame.draw.circle(self.screen, (star.brightness,)*3, (int(sx), int(sy)), 1)

        pixel_scale = self.get_current_pixel_scale()
        
        # Траектории
        if self.show_trails:
            for body in self.bodies:
                if len(body.trail) > 1:
                    screen_points = []
                    for pos in body.trail:
                        px = int(pos[0] * pixel_scale * self.zoom + self.offset_x)
                        py = int(pos[1] * pixel_scale * self.zoom + self.offset_y)
                        
                        if -500 < px < self.width + 500 and -500 < py < self.height + 500:
                            screen_points.append((px, py))
                    
                    if len(screen_points) > 1:
                        if body.name == "Moon":
                            pygame.draw.lines(self.screen, (255, 255, 255, 150), False, screen_points, 2)
                        else:
                            pygame.draw.lines(self.screen, body.color, False, screen_points, 1)

        # Планеты
        for body in self.bodies:
            sx, sy = body.get_screen_pos(self.offset_x, self.offset_y, self.zoom, pixel_scale, 1.0)
            radius = body.get_draw_radius(self.zoom, 1.0)
            
            if -radius*2 < sx < self.width + radius*2 and -radius*2 < sy < self.height + radius*2:
                if body == self.selected_body:
                    pygame.draw.circle(self.screen, (100, 255, 100), (sx, sy), radius + 5, 2)
                    
                pygame.draw.circle(self.screen, body.color, (sx, sy), radius)
                
                if self.show_vectors:
                    ex, ey = body.get_velocity_tip_pos(sx, sy, self.zoom, pixel_scale, 1.0)
                    if math.hypot(ex-sx, ey-sy) > 2:
                        color = (0, 255, 100)
                        if self.interaction_mode == 'drag_vector' and self.active_body == body:
                            color = (255, 255, 0)
                        self.draw_arrow((sx, sy), (ex, ey), color, 2, self.zoom)

                if radius > 3:
                    txt = self.font_name.render(body.name, True, (200, 200, 200))
                    self.screen.blit(txt, (sx + radius + 5, sy - 5))
        
        # Сообщения о столкновениях (рисуем после планет, но перед UI)
        self.draw_collision_messages()
        
        # Кнопка информации с эффектом наведения
        button_center_x = int(40 * self.scale_factor)
        button_center_y = int(40 * self.scale_factor)
        button_radius = int(20 * self.scale_factor)
        
        self.info_button_rect = pygame.Rect(
            button_center_x - button_radius,
            button_center_y - button_radius,
            button_radius * 2,
            button_radius * 2
        )
        
        button_color = (80, 90, 130) if self.info_button_hovered else (60, 70, 100)
        pygame.draw.circle(self.screen, button_color, (button_center_x, button_center_y), button_radius)
        border_color = (120, 160, 255) if self.info_button_hovered else (100, 150, 255)
        pygame.draw.circle(self.screen, border_color, (button_center_x, button_center_y), button_radius, int(2 * self.scale_factor))
        
        info_text = self.font_subtitle.render("i", True, (200, 220, 255))
        self.screen.blit(info_text, (button_center_x - info_text.get_width()//2, 
                                    button_center_y - info_text.get_height()//2))
        
        # Информационная панель (если открыта или в процессе анимации)
        self.draw_info_panel()
        
        self.draw_title_bar()
        self.manager.draw_ui(self.screen)
        pygame.display.flip()

    def update_physics(self):
        if not self.paused and self.interaction_mode != 'drag_body':
            # Проверяем столкновения перед обновлением физики
            self.check_collisions()
            
            has_moon = any(body.name == "Moon" for body in self.bodies)
            substeps = 100 if has_moon else 20
            
            dt = (TIME_STEP * self.time_scale) / substeps
            
            for _ in range(substeps):
                for body in self.bodies:
                    body.calculate_forces(self.bodies)
                    acceleration = body.force_vector / body.mass
                    body.velocity += acceleration * (dt / 2)
                
                for body in self.bodies:
                    body.position += body.velocity * dt
                
                for body in self.bodies:
                    body.calculate_forces(self.bodies)
                    acceleration = body.force_vector / body.mass
                    body.velocity += acceleration * (dt / 2)
            
            for body in self.bodies:
                body.update_trail()

    def run(self):
        running = True
        while running:
            running = self.handle_input()
            self.update_physics()
            self.update_camera_animation()
            self.draw()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    sim = SolarSystemSim()
    sim.run()

#py -3.12 s.py 
#py -3.12 -m pip install pygame
#py -3.12 -m pip install pggui